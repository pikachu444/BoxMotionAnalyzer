import pandas as pd
from PySide6.QtCore import QObject, Signal
from src.config import config_app
from src.config.data_columns import FACE_PREFIX_TO_INFO
from analysis.slicer import Slicer
from analysis.parser import Parser
from analysis.smoother import MarkerSmoother
from analysis.pose_optimizer import PoseOptimizer
from analysis.velocity_calculator import VelocityCalculator
from analysis.frame_analyzer import FrameAnalyzer

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
        파싱된 데이터가 있으면 재사용합니다.
        """
        try:
            data = None
            # 1. 파싱 단계
            if parsed_data is not None:
                self.log_message.emit("[1/6] Using cached parsed data...")
                data = parsed_data
            else:
                self.log_message.emit("[1/6] Parsing data...")
                data = self.parser.process(header_info, raw_data)
            self.log_message.emit(f"    Parser output shape: {data.shape}")

            # 2. 슬라이싱 단계
            # 주의: 파서의 결과물(wide-format)을 슬라이싱해야 함
            self.log_message.emit("[2/6] Slicing data...")
            slicer = Slicer(
                filter_by=gui_config.get('slice_filter_by', 'time'),
                start_val=gui_config.get('slice_start_val'),
                end_val=gui_config.get('slice_end_val')
            )
            # Slicer는 raw_df가 아닌, 파싱된 df를 슬라이싱해야 함.
            # Slicer의 로직이 Time 인덱스를 사용하므로 파싱된 데이터에 적용 가능.
            data = slicer.process(data)
            self.log_message.emit(f"    Slicer done. Shape: {data.shape}")

            # 3. MarkerSmoother 실행
            self.log_message.emit("[3/6] Smoothing markers...")
            data = self.smoother.process(data)
            self.log_message.emit(f"    Smoother done. Shape: {data.shape}")

            # 4. PoseOptimizer 실행
            self.log_message.emit("[4/6] Optimizing pose...")
            data = self.pose_optimizer.process(data)
            self.log_message.emit(f"    PoseOptimizer done. Shape: {data.shape}")

            # 5. VelocityCalculator 실행
            self.log_message.emit("[5/6] Calculating velocity...")
            data = self.velocity_calculator.process(data)
            self.log_message.emit(f"    VelocityCalculator done. Shape: {data.shape}")

            # 6. FrameAnalyzer 실행
            self.log_message.emit("[6/6] Analyzing frames...")
            final_result = self.frame_analyzer.process(data)
            self.log_message.emit(f"    FrameAnalyzer done. Shape: {final_result.shape}")

            self.log_message.emit("\nAnalysis pipeline completed successfully.")
            self.analysis_finished.emit(final_result)

        except Exception as e:
            import traceback
            self.log_message.emit(f"[ERROR] An error occurred in the pipeline: {e}")
            self.log_message.emit(f"Traceback: {traceback.format_exc()}")
            self.analysis_finished.emit(pd.DataFrame())
