import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal
from src.config import config_app, config_analysis
from src.config.data_columns import FACE_PREFIX_TO_INFO, TimeCols
from src.analysis.pipeline.slicer import Slicer
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.smoother import MarkerSmoother
from src.analysis.pipeline.pose_optimizer import PoseOptimizer
from src.analysis.pipeline.velocity_calculator import VelocityCalculator
from src.analysis.pipeline.frame_analyzer import FrameAnalyzer
from src.analysis.pipeline.resampling_options import build_effective_analysis_options
from src.analysis.pipeline.resampler import UniformResampler
from src.analysis.pipeline.validator import DataValidator

class PipelineController(QObject):
    log_message = Signal(str)
    analysis_finished = Signal(pd.DataFrame)
    analysis_failed = Signal(str)

    def __init__(self):
        super().__init__()
        # 파서 모듈은 MainApp에서도 사용되므로, 여기서는 초기화하지 않음.
        # 또는, 독립적인 인스턴스를 가질 수도 있음. 여기서는 후자를 가정.
        self.parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        self.smoother = MarkerSmoother()
        self.pose_optimizer = PoseOptimizer(
            face_definitions=getattr(config_app, 'FACE_DEFINITIONS', {}),
            local_box_corners=config_app.LOCAL_BOX_CORNERS
        )
        self.velocity_calculator = VelocityCalculator()
        self.frame_analyzer = FrameAnalyzer(
            vertical_axis_idx=config_app.WORLD_VERTICAL_AXIS_INDEX,
            floor_level=config_app.FLOOR_LEVEL
        )

    def _execute_analysis_from_parsed(self, gui_config: dict, parsed_data: pd.DataFrame) -> pd.DataFrame:
        if self._is_result_resampling_enabled(gui_config):
            return self._execute_result_resampling(gui_config, parsed_data)
        return self._execute_analysis_single_pass(gui_config, parsed_data)

    def _apply_box_dimensions_from_config(self, gui_config: dict) -> None:
        box_dims = gui_config.get('box_dimensions')
        if box_dims is None:
            return

        normalized_dims = np.array(box_dims, dtype=float)
        if normalized_dims.shape != (3,) or np.any(normalized_dims <= 0):
            raise ValueError("Box dimensions must include positive L, W, and H values.")

        config_app.BOX_DIMS = normalized_dims
        config_app.LOCAL_BOX_CORNERS = config_app.calculate_local_box_corners(normalized_dims)
        self.pose_optimizer.local_box_corners = config_app.LOCAL_BOX_CORNERS
        self.velocity_calculator.local_box_corners = config_app.LOCAL_BOX_CORNERS

    def _execute_analysis_single_pass(self, gui_config: dict, parsed_data: pd.DataFrame) -> pd.DataFrame:
        self._apply_box_dimensions_from_config(gui_config)
        analysis_options = gui_config.get('analysis_options', {})
        processing_mode = gui_config.get('processing_mode', 'standard')
        effective_analysis_options = build_effective_analysis_options(analysis_options, 1)
        self.smoother.configure(effective_analysis_options)
        self.velocity_calculator.configure(effective_analysis_options)

        self.log_message.emit(f"[INFO] Using Box Dimensions (L,W,H): {config_app.BOX_DIMS}")
        self.log_message.emit(f"[INFO] Processing mode: {processing_mode}")
        data = parsed_data
        self.log_message.emit(f"    Parser output shape: {data.shape}")

        # 1.5 데이터 검증
        # - Raw Data 검증은 DataLoader 단계에서 이미 수행됨 (Time/Frame 존재 여부 등)
        # - 여기서는 데이터 길이(Rows) 등 분석 가능 여부만 최소한으로 확인
        self.log_message.emit("[1.5/8] Validating data sufficiency...")
        DataValidator.validate_data_sufficiency(data, min_rows=50)

        # Note: 파서(Parser) 결과에 대한 컬럼 검증은 제거함.
        # 원본 데이터에 필수 컬럼이 있다면 Parser가 처리해야 하며,
        # 여기서 에러를 내면 사용자에게 원본 파일 문제로 오인될 수 있음.

        # 2. 패딩된 슬라이스 생성
        self.log_message.emit("[2/8] Slicing data with padding...")
        original_start = gui_config.get('slice_start_val')
        original_end = gui_config.get('slice_end_val')
        padding_size_frames = (
            config_analysis.SMOOTHING_PADDING_SIZE
            if analysis_options.get('enable_marker_smoothing', True)
            else 0
        )
        time_index = pd.Series(data.index)
        time_diffs = time_index.diff().dropna()
        mean_delta_t = time_diffs.mean() if not time_diffs.empty else 0
        time_padding = padding_size_frames * mean_delta_t if mean_delta_t > 0 else 0
        padded_start = max(original_start - time_padding, time_index.min())
        padded_end = min(original_end + time_padding, time_index.max())

        self.log_message.emit(f"    Original slice: {original_start:.2f}s - {original_end:.2f}s")
        self.log_message.emit(f"    Padding: {padding_size_frames} frames ({time_padding:.3f}s)")
        self.log_message.emit(f"    Padded slice for processing: {padded_start:.2f}s - {padded_end:.2f}s")

        slicer_for_padding = Slicer(
            filter_by=gui_config.get('slice_filter_by', 'time'),
            start_val=padded_start,
            end_val=padded_end
        )
        padded_data = slicer_for_padding.process(data)
        self.log_message.emit(f"    Padded slicer done. Shape: {padded_data.shape}")

        # 3. 스무딩
        if effective_analysis_options.get('enable_marker_smoothing', True):
            self.log_message.emit("[3/8] Smoothing markers...")
            data_to_process = self.smoother.process(padded_data)
            self.log_message.emit(f"    Smoother done. Shape: {data_to_process.shape}")
        else:
            self.log_message.emit("[3/8] Marker smoothing skipped by processing mode.")
            data_to_process = padded_data.copy()

        # --- 전략적 분기점 ---
        trimming_strategy = effective_analysis_options.get('trimming_strategy', config_analysis.TRIMMING_STRATEGY)
        self.log_message.emit(f"\n[INFO] Using Trimming Strategy: '{trimming_strategy}'")

        slicer_for_trimming = Slicer(
            filter_by=gui_config.get('slice_filter_by', 'time'),
            start_val=original_start,
            end_val=original_end
        )

        if trimming_strategy == 'early':
            # 4. 조기 트리밍 (Early Trimming)
            self.log_message.emit("[4/8] Trimming data early (before pose/velocity)...")
            data_to_process = slicer_for_trimming.process(data_to_process)
            self.log_message.emit(f"    Trimming done. Shape for analysis: {data_to_process.shape}")
        else:
            # 5. 후기 트리밍 (Late Trimming)
            self.log_message.emit("[4/8] data will be trimmed after all calculations...")

        # 5. 자세 최적화
        self.log_message.emit("[5/8] Optimizing pose...")
        data_to_process = self.pose_optimizer.process(data_to_process)
        self.log_message.emit(f"    PoseOptimizer done. Shape: {data_to_process.shape}")

        # 6. 속도 계산
        self.log_message.emit("[6/8] Calculating velocity...")
        data_to_process = self.velocity_calculator.process(data_to_process)
        self.log_message.emit(f"    VelocityCalculator done. Shape: {data_to_process.shape}")

        # 7. 최종 프레임 분석
        self.log_message.emit("[7/8] Analyzing frames...")
        final_result = self.frame_analyzer.process(data_to_process)
        self.log_message.emit(f"    FrameAnalyzer done. Shape: {final_result.shape}")

        if trimming_strategy == 'late':
            # 8. 후기 트리밍 (Late Trimming)
            self.log_message.emit("[8/8] Trimming data late (after all calculations)...")
            final_result = slicer_for_trimming.process(final_result)
            self.log_message.emit(f"    Trimming done. Final shape: {final_result.shape}")

        self.log_message.emit("\nAnalysis pipeline completed successfully.")
        return final_result

    def _is_result_resampling_enabled(self, gui_config: dict) -> bool:
        enabled = gui_config.get('enable_result_resampling', gui_config.get('enable_resampling', False))
        return bool(enabled) and self._get_result_resampling_factor(gui_config) > 1

    def _get_result_resampling_factor(self, gui_config: dict) -> int:
        return int(gui_config.get('result_resampling_factor', gui_config.get('resampling_factor') or 1) or 1)

    def _is_result_resampling_range_limited(self, gui_config: dict) -> bool:
        return bool(
            gui_config.get(
                'limit_result_resampling_to_range',
                gui_config.get('limit_resampling_to_range', False),
            )
        )

    def _copy_config_for_pass(self, gui_config: dict, **overrides) -> dict:
        pass_config = dict(gui_config)
        pass_config['analysis_options'] = dict(gui_config.get('analysis_options', {}))
        pass_config.update(overrides)
        pass_config['enable_result_resampling'] = False
        pass_config['limit_result_resampling_to_range'] = False
        pass_config['result_resampling_factor'] = 1
        # Legacy key fallback: make sure a baseline pass never performs old input resampling.
        pass_config['enable_resampling'] = False
        pass_config['limit_resampling_to_range'] = False
        pass_config['resampling_factor'] = 1
        return pass_config

    def _validate_resampling_range(self, gui_config: dict, parsed_data: pd.DataFrame) -> tuple[float, float]:
        original_start = float(gui_config.get('slice_start_val'))
        original_end = float(gui_config.get('slice_end_val'))
        range_start = gui_config.get('result_resampling_range_start', gui_config.get('resampling_range_start'))
        range_end = gui_config.get('result_resampling_range_end', gui_config.get('resampling_range_end'))
        if range_start is None or range_end is None:
            raise ValueError("Range-limited result resampling requires start and end times.")

        range_start = float(range_start)
        range_end = float(range_end)
        if range_start >= range_end:
            raise ValueError("Result resampling range start must be smaller than end.")

        tolerance = 1e-9
        if range_start < original_start - tolerance or range_end > original_end + tolerance:
            raise ValueError("Result resampling range must stay inside the selected slice range.")

        data_min = float(parsed_data.index.min())
        data_max = float(parsed_data.index.max())
        if range_start < data_min - tolerance or range_end > data_max + tolerance:
            raise ValueError("Result resampling range must stay inside the loaded slice data.")

        return range_start, range_end

    def _merge_result_resampling_rows(
        self,
        baseline_result: pd.DataFrame,
        resampled_result: pd.DataFrame,
        range_start: float,
        range_end: float,
    ) -> pd.DataFrame:
        if baseline_result.empty or resampled_result.empty:
            return baseline_result.copy()

        baseline_index = baseline_result.index.to_numpy(dtype=float)
        resampled_index = resampled_result.index.to_numpy(dtype=float)
        tolerance = 1e-9
        inside_range = (resampled_index >= range_start - tolerance) & (resampled_index <= range_end + tolerance)
        new_timestamp_mask = np.array(
            [not np.any(np.isclose(timestamp, baseline_index, rtol=0.0, atol=tolerance)) for timestamp in resampled_index]
        )
        rows_to_insert = resampled_result.loc[inside_range & new_timestamp_mask]

        merged = pd.concat([baseline_result, rows_to_insert], axis=0).sort_index(kind='mergesort')
        merged = merged[~merged.index.duplicated(keep='first')].copy()
        if TimeCols.FRAME in merged.columns:
            merged[TimeCols.FRAME] = np.arange(len(merged), dtype=int)
        return merged

    def _execute_result_resampling(self, gui_config: dict, parsed_data: pd.DataFrame) -> pd.DataFrame:
        resampling_factor = self._get_result_resampling_factor(gui_config)
        baseline_config = self._copy_config_for_pass(gui_config)
        self.log_message.emit("[INFO] Running baseline processing before result resampling...")
        baseline_result = self._execute_analysis_single_pass(baseline_config, parsed_data)

        if self._is_result_resampling_range_limited(gui_config):
            range_start, range_end = self._validate_resampling_range(gui_config, parsed_data)
            self.log_message.emit(
                "[INFO] Result resampling enabled for selected range: "
                f"{range_start:.3f}s - {range_end:.3f}s at {resampling_factor}x"
            )
            result_to_resample = baseline_result.loc[range_start:range_end]
        else:
            range_start = float(baseline_result.index.min())
            range_end = float(baseline_result.index.max())
            self.log_message.emit(
                "[INFO] Result resampling enabled for full slice: "
                f"{range_start:.3f}s - {range_end:.3f}s at {resampling_factor}x"
            )
            result_to_resample = baseline_result

        self.log_message.emit("[INFO] Interpolating processed result rows...")
        resampled_result = UniformResampler(resampling_factor).process(result_to_resample)

        merged = self._merge_result_resampling_rows(
            baseline_result,
            resampled_result,
            range_start,
            range_end,
        )
        inserted_rows = len(merged) - len(baseline_result)
        self.log_message.emit(f"[INFO] Inserted {inserted_rows} interpolated result rows.")
        self.log_message.emit("\nResult resampling pipeline completed successfully.")
        return merged

    def process_parsed_data(self, gui_config: dict, parsed_data: pd.DataFrame) -> pd.DataFrame:
        return self._execute_analysis_from_parsed(gui_config, parsed_data)

    def _run_analysis_from_parsed(self, gui_config: dict, parsed_data: pd.DataFrame):
        try:
            final_result = self._execute_analysis_from_parsed(gui_config, parsed_data)
            self.analysis_finished.emit(final_result)
        except Exception as e:
            import traceback
            error_msg = f"[ERROR] An error occurred in the pipeline: {e}"
            self.log_message.emit(error_msg)
            self.log_message.emit(f"Traceback: {traceback.format_exc()}")
            self.analysis_finished.emit(pd.DataFrame())
            self.analysis_failed.emit(str(e))

    def run_analysis(self, gui_config: dict, header_info: dict, raw_data: pd.DataFrame, parsed_data: pd.DataFrame = None):
        """
        전체 분석 파이프라인을 순차적으로 실행합니다.
        """
        if parsed_data is not None:
            self.log_message.emit("[1/8] Using cached parsed data...")
            self._run_analysis_from_parsed(gui_config, parsed_data)
            return

        self.log_message.emit("[1/8] Parsing data...")
        data = self.parser.process(header_info, raw_data)
        self._run_analysis_from_parsed(gui_config, data)

    def run_analysis_from_parsed(self, gui_config: dict, parsed_data: pd.DataFrame):
        """
        이미 파싱된 slice 데이터를 대상으로 processing 단계부터 실행합니다.
        """
        self.log_message.emit("[1/8] Using parsed slice data...")
        self._run_analysis_from_parsed(gui_config, parsed_data)
