import pandas as pd
from PySide6.QtCore import QObject, Signal
import app_config as config
from analysis.slicer import Slicer
from analysis.parser import Parser
from analysis.smoother import MarkerSmoother
from analysis.pose_optimizer import PoseOptimizer
from analysis.velocity_calculator import VelocityCalculator
from analysis.frame_analyzer import FrameAnalyzer

class PipelineController(QObject):
    """
    Controls the data analysis workflow by orchestrating analysis modules.
    """
    log_message = Signal(str)
    analysis_finished = Signal(pd.DataFrame)

    def __init__(self):
        super().__init__()
        # 분석 모듈들을 초기화. 의존성은 config 파일에서 주입.
        self.parser = Parser(face_prefix_map=config.FACE_PREFIX_TO_INFO)
        self.smoother = MarkerSmoother() # 기본값 사용
        self.pose_optimizer = PoseOptimizer(
            box_dims=config.BOX_DIMS,
            face_definitions=getattr(config, 'FACE_DEFINITIONS', {}),
            local_box_corners=config.LOCAL_BOX_CORNERS
        )
        self.velocity_calculator = VelocityCalculator() # 기본값 사용
        self.frame_analyzer = FrameAnalyzer(
            vertical_axis_idx=config.WORLD_VERTICAL_AXIS_INDEX,
            floor_level=config.FLOOR_LEVEL
        )

    def run_analysis(self, gui_config: dict, header_info: dict, raw_data: pd.DataFrame):
        """
        Runs the full analysis pipeline sequentially.
        """
        try:
            # 1. Slicer 초기화 및 실행
            self.log_message.emit("[1/6] Slicing data...")
            slicer = Slicer(
                filter_by=gui_config.get('slice_filter_by', 'time'),
                start_val=gui_config.get('slice_start_val'),
                end_val=gui_config.get('slice_end_val')
            )
            data = slicer.process(raw_data)
            self.log_message.emit(f"    Slicer done. Shape: {data.shape}")

            # 2. Parser 실행
            self.log_message.emit("[2/6] Parsing data...")
            data = self.parser.process(header_info, data)
            self.log_message.emit(f"    Parser done. Shape: {data.shape}")

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
