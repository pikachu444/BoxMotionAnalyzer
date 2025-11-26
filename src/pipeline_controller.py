import pandas as pd
from PySide6.QtCore import QObject, Signal
from src.config import config_app, config_analysis
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.analysis.slicer import Slicer
from src.analysis.parser import Parser
from src.analysis.smoother import MarkerSmoother
from src.analysis.pose_optimizer import PoseOptimizer
from src.analysis.velocity_calculator import VelocityCalculator
from src.analysis.frame_analyzer import FrameAnalyzer
from src.analysis.validator import DataValidator

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

    def run_analysis(self, gui_config: dict, header_info: dict, raw_data: pd.DataFrame, parsed_data: pd.DataFrame = None):
        """
        전체 분석 파이프라인을 순차적으로 실행합니다.
        """
        try:
            self.log_message.emit(f"[INFO] Using Box Dimensions (L,W,H): {config_app.BOX_DIMS}")
            # 파싱된 데이터가 있으면 재사용하고, 스무딩을 위해 패딩/트리밍을 수행합니다.

            # 1. 파싱 단계
            if parsed_data is not None:
                self.log_message.emit("[1/8] Using cached parsed data...")
                data = parsed_data
            else:
                self.log_message.emit("[1/8] Parsing data...")
                data = self.parser.process(header_info, raw_data)
            self.log_message.emit(f"    Parser output shape: {data.shape}")

            # 1.5 데이터 검증
            self.log_message.emit("[1.5/8] Validating data...")
            DataValidator.validate_data_sufficiency(data, min_rows=50)
            
            # Rigid Body 필수 컬럼 검증
            from src.config.data_columns import PoseCols, TimeCols
            required_rb_cols = [TimeCols.TIME, PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z]
            DataValidator.validate_required_columns(data, required_rb_cols)

            # 2. 패딩된 슬라이스 생성
            self.log_message.emit("[2/8] Slicing data with padding...")
            original_start = gui_config.get('slice_start_val')
            original_end = gui_config.get('slice_end_val')
            padding_size_frames = config_analysis.SMOOTHING_PADDING_SIZE
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
            self.log_message.emit("[3/8] Smoothing markers...")
            data_to_process = self.smoother.process(padded_data)
            self.log_message.emit(f"    Smoother done. Shape: {data_to_process.shape}")

            # --- 전략적 분기점 ---
            trimming_strategy = config_analysis.TRIMMING_STRATEGY
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
            else :
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
            self.analysis_finished.emit(final_result)

        except Exception as e:
            import traceback
            error_msg = f"[ERROR] An error occurred in the pipeline: {e}"
            self.log_message.emit(error_msg)
            self.log_message.emit(f"Traceback: {traceback.format_exc()}")
            self.analysis_finished.emit(pd.DataFrame())
            self.analysis_failed.emit(str(e))
