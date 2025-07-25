import pandas as pd
from typing import Dict, List
import app_config as config

class Parser:
    """
    "long-format"의 원본 DataFrame을 분석에 용이한 "wide-format"으로 변환합니다.
    AlignBoxInputGenbyExperiment.py 스크립트의 핵심 로직을 클래스 형태로 이식한 것입니다.
    """

    def __init__(self):
        self.face_prefix_map = config.FACE_PREFIX_TO_INFO

    def process(self, header_info: Dict[str, List[str]], raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        원본 DataFrame을 파싱하여 wide-format DataFrame으로 변환합니다.
        """
        if raw_df.empty:
            return pd.DataFrame()

        type_header = header_info.get('type', [])
        name_header = header_info.get('name', [])
        parent_header = header_info.get('parent', [])

        processed_frames_data = []
        ordered_unique_marker_ids = []
        seen_marker_ids = set()

        for index, row in raw_df.iterrows():
            frame_number = row.get('Frame', str(index))
            time_value = row.get('Time', "0.0")

            current_frame_dict = {'Frame': frame_number, 'Time': float(time_value)}

            for i in range(2, len(row)):
                col_name = f'col_{i}'
                if col_name not in row or pd.isna(row[col_name]): continue

                if i >= len(type_header) or i >= len(name_header) or i >= len(parent_header): continue

                current_type = type_header[i]
                current_parent = parent_header[i]
                full_marker_name = name_header[i]

                is_target_marker_x = (
                    current_type == "Rigid Body Marker" and
                    current_parent and
                    ':' in full_marker_name and
                    (i + 2) < len(row)
                )

                if is_target_marker_x:
                    try:
                        name_parts = full_marker_name.split(':', 1)
                        if len(name_parts) < 2 or not name_parts[1]: continue

                        marker_id = name_parts[1].replace(" ", "_")

                        x_val = float(row[f'col_{i}'])
                        y_val = float(row[f'col_{i+1}'])
                        z_val = float(row[f'col_{i+2}'])

                        if marker_id not in seen_marker_ids:
                            ordered_unique_marker_ids.append(marker_id)
                            seen_marker_ids.add(marker_id)

                        current_frame_dict[f"{marker_id}_X"] = x_val
                        current_frame_dict[f"{marker_id}_Y"] = y_val
                        current_frame_dict[f"{marker_id}_Z"] = z_val

                    except (ValueError, IndexError):
                        continue

            processed_frames_data.append(current_frame_dict)

        if not processed_frames_data:
            return pd.DataFrame()

        final_df = pd.DataFrame(processed_frames_data)

        if 'Time' in final_df.columns:
            final_df['Time'] = pd.to_numeric(final_df['Time'])
            final_df.set_index('Time', inplace=True)

        if 'Frame' in final_df.columns:
            final_df['Frame'] = pd.to_numeric(final_df['Frame'])

        cols_ordered = ['Frame']
        for marker_id in sorted(list(ordered_unique_marker_ids)):
            cols_ordered.extend([f"{marker_id}_X", f"{marker_id}_Y", f"{marker_id}_Z"])

        final_cols = [col for col in cols_ordered if col in final_df.columns]

        return final_df[final_cols]
