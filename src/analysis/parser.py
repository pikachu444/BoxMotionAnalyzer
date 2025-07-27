import pandas as pd
from typing import Dict, List
from config.data_columns import TimeCols, RawMarkerCols

class Parser:
    """
    "long-format"의 원본 DataFrame을 분석에 용이한 "wide-format"으로 변환합니다.
    AlignBoxInputGenbyExperiment.py 스크립트의 핵심 로직을 클래스 형태로 이식한 것입니다.
    """

    def __init__(self, face_prefix_map: Dict[str, str]):
        """
        Parser를 초기화합니다.

        Args:
            face_prefix_map (Dict[str, str]): 마커 접두사와 면(Face) 정보를 매핑하는 딕셔너리.
        """
        self.face_prefix_map = face_prefix_map

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
            frame_number = row.get(TimeCols.FRAME, str(index))
            time_value = row.get(TimeCols.TIME, "0.0")

            current_frame_dict = {TimeCols.FRAME: frame_number, TimeCols.TIME: float(time_value)}

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

                        current_frame_dict[f"{marker_id}{RawMarkerCols.X_SUFFIX}"] = x_val
                        current_frame_dict[f"{marker_id}{RawMarkerCols.Y_SUFFIX}"] = y_val
                        current_frame_dict[f"{marker_id}{RawMarkerCols.Z_SUFFIX}"] = z_val

                    except (ValueError, IndexError):
                        continue

            processed_frames_data.append(current_frame_dict)

        if not processed_frames_data:
            return pd.DataFrame()

        final_df = pd.DataFrame(processed_frames_data)

        if TimeCols.TIME in final_df.columns:
            final_df[TimeCols.TIME] = pd.to_numeric(final_df[TimeCols.TIME])
            final_df.set_index(TimeCols.TIME, inplace=True)

        if TimeCols.FRAME in final_df.columns:
            final_df[TimeCols.FRAME] = pd.to_numeric(final_df[TimeCols.FRAME])

        cols_ordered = [TimeCols.FRAME]
        for marker_id in sorted(list(ordered_unique_marker_ids)):
            cols_ordered.extend([f"{marker_id}{RawMarkerCols.X_SUFFIX}", f"{marker_id}{RawMarkerCols.Y_SUFFIX}", f"{marker_id}{RawMarkerCols.Z_SUFFIX}"])

        final_cols = [col for col in cols_ordered if col in final_df.columns]

        return final_df[final_cols]
