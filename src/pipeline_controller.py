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

class PipelineController(QObject):
    log_message = Signal(str)
    analysis_finished = Signal(pd.DataFrame)

    def __init__(self):
        super().__init__()
        # 파서 모듈은 MainApp에서도 사용되므로, 여기서는 초기화하지 않음.
        # 또는, 독립적인 인스턴스를 가질 수도 있음. 여기서는 후자를 가정.
        self.parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        self.smoother = MarkerSmoother()
        self.pose_optimizer = PoseOptimizer(
            box_dims=config_app.BOX_DIMS,
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
        파싱된 데이터가 있으면 재사용하고, 스무딩을 위해 패딩/트리밍을 수행합니다.
        """
        try:
            # 1. 파싱 단계
            self.log_message.emit("[1/7] Parsing data...")
            if parsed_data is not None:
                data = parsed_data
                self.log_message.emit("    Using cached parsed data.")
            else:
                data = self.parser.process(header_info, raw_data)
            self.log_message.emit(f"    Parser output shape: {data.shape}")

            # 2. 패딩을 포함한 슬라이싱 단계
            self.log_message.emit("[2/7] Slicing data with padding...")
            padding_size = config_analysis.BUTTERWORTH_PAD_SIZE
            slicer_with_padding = Slicer(
                filter_by=gui_config.get('slice_filter_by', 'time'),
                start_val=gui_config.get('slice_start_val'),
                end_val=gui_config.get('slice_end_val'),
                padding_size=padding_size
            )
            padded_data = slicer_with_padding.process(data)
            self.log_message.emit(f"    Padded slice shape: {padded_data.shape}")

            # 3. MarkerSmoother 실행 (패딩된 데이터에 적용)
            self.log_message.emit("[3/7] Smoothing markers on padded data...")
            smoothed_padded_data = self.smoother.process(padded_data)
            self.log_message.emit(f"    Smoother output shape: {smoothed_padded_data.shape}")

            # 4. 트리밍 단계 (패딩 제거)
            self.log_message.emit("[4/7] Trimming data to original slice...")
            slicer_without_padding = Slicer(
                filter_by=gui_config.get('slice_filter_by', 'time'),
                start_val=gui_config.get('slice_start_val'),
                end_val=gui_config.get('slice_end_val'),
                padding_size=0  # 패딩 없음
            )
            data = slicer_without_padding.process(smoothed_padded_data)
            self.log_message.emit(f"    Trimmed data shape: {data.shape}")

            # 5. PoseOptimizer 실행
            self.log_message.emit("[5/7] Optimizing pose...")
            data = self.pose_optimizer.process(data)
            self.log_message.emit(f"    PoseOptimizer done. Shape: {data.shape}")

            # 6. VelocityCalculator 실행
            self.log_message.emit("[6/7] Calculating velocity...")
            data = self.velocity_calculator.process(data)
            self.log_message.emit(f"    VelocityCalculator done. Shape: {data.shape}")

            # 7. FrameAnalyzer 실행
            self.log_message.emit("[7/7] Analyzing frames...")
            final_result = self.frame_analyzer.process(data)
            self.log_message.emit(f"    FrameAnalyzer done. Shape: {final_result.shape}")

            self.log_message.emit("\nAnalysis pipeline completed successfully.")
            self.analysis_finished.emit(final_result)

        except Exception as e:
            import traceback
            self.log_message.emit(f"[ERROR] An error occurred in the pipeline: {e}")
            self.log_message.emit(f"Traceback: {traceback.format_exc()}")
            self.analysis_finished.emit(pd.DataFrame())
