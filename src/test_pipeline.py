import pandas as pd
import numpy as np
import os
import sys

# Add the project root to the Python path to allow for absolute imports
# This is necessary to run this script directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.pipeline_controller import PipelineController
from src.config import config_analysis
from src.config.data_columns import TimeCols, PoseCols, RawMarkerCols

def create_mock_data(num_rows=1000, fs=200):
    """Creates a mock DataFrame for testing the pipeline."""
    time = np.arange(num_rows) / fs
    df = pd.DataFrame({
        TimeCols.TIME: time,
    })
    df.set_index(TimeCols.TIME, inplace=True)

    # Add necessary pose and marker columns with dummy data
    for col in [PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z,
                PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]:
        df[col] = np.sin(df.index * 2 * np.pi * 1) # Dummy sine wave

    for i in range(1, 5): # Assume 4 markers
        for suffix in [RawMarkerCols.X_SUFFIX, RawMarkerCols.Y_SUFFIX, RawMarkerCols.Z_SUFFIX]:
            df[f'B{i}{suffix}'] = np.random.randn(num_rows)

    header_info = {'some_header_key': 'some_value'} # Mock header
    return header_info, df

def test_pipeline_strategy(strategy):
    """Tests the pipeline with a given trimming strategy."""
    print(f"\n--- Testing TRIMMING_STRATEGY: '{strategy}' ---")

    # Set the configuration for this test run
    config_analysis.TRIMMING_STRATEGY = strategy

    # 1. Setup
    header_info, mock_data = create_mock_data(num_rows=2000, fs=200) # 10 seconds of data at 200Hz
    controller = PipelineController()

    # Mock GUI config
    slice_start = 2.0  # seconds
    slice_end = 8.0    # seconds
    gui_config = {
        'slice_filter_by': 'time',
        'slice_start_val': slice_start,
        'slice_end_val': slice_end,
    }

    # Connect a simple slot to catch the result
    result_container = {}
    def on_finish(result_df):
        result_container['df'] = result_df
        print("Pipeline finished. Result received.")

    controller.analysis_finished.connect(on_finish)

    # 2. Run
    # In a real Qt app, this would be a QThread, but for this test, we run it directly.
    # The controller's run_analysis is blocking, so we can check the result after it's done.
    controller.run_analysis(gui_config, header_info, raw_data=None, parsed_data=mock_data)

    # 3. Assert
    assert 'df' in result_container, "Pipeline did not emit the finished signal with data."
    result_df = result_container['df']

    assert not result_df.empty, "Pipeline returned an empty DataFrame."

    # The final result should always be trimmed to the user's selection
    expected_num_rows = int((slice_end - slice_start) * 200) # fs=200Hz

    # Allow for a small tolerance due to floating point comparisons
    # The number of samples should be very close to (duration * sampling_rate)
    assert abs(len(result_df) - expected_num_rows) <= 1, \
        f"Strategy '{strategy}': Expected ~{expected_num_rows} rows, but got {len(result_df)}."

    print(f"Resulting DataFrame has {len(result_df)} rows. (Expected: ~{expected_num_rows})")
    print(f"Assertion successful for strategy '{strategy}'.")
    return True

if __name__ == '__main__':
    print("Starting pipeline logic test...")

    # Store original strategy
    original_strategy = config_analysis.TRIMMING_STRATEGY

    try:
        # Test 'early' trimming
        test_pipeline_strategy('early')

        # Test 'late' trimming
        test_pipeline_strategy('late')

        print("\n✅ All pipeline strategy tests passed successfully!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        # Restore original strategy to avoid side-effects
        config_analysis.TRIMMING_STRATEGY = original_strategy
        print(f"\nRestored original TRIMMING_STRATEGY to '{original_strategy}'.")
