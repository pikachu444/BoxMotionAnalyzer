import pandas as pd
from src.config.data_columns import TimeCols, RawMarkerCols, RigidBodyCols

class Parser:
    """
    "long-format"의 원본 DataFrame을 분석에 용이한 "wide-format"으로 변환합니다.
    AlignBoxInputGenbyExperiment.py 스크립트의 핵심 로직을 클래스 형태로 이식한 것입니다.
    """

    def __init__(self, face_prefix_map: dict[str, str]):
        """
        Parser를 초기화합니다.

        Args:
            face_prefix_map (dict[str, str]): 마커 접두사와 면(Face) 정보를 매핑하는 딕셔너리.
        """
        self.face_prefix_map = face_prefix_map

    def process(self, header_info: dict[str, list[str]], raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        원본 DataFrame을 파싱하여 wide-format DataFrame으로 변환합니다.
        """
        if raw_df.empty:
            return pd.DataFrame()

        type_header = header_info.get('type', [])
        name_header = header_info.get('name', [])
        parent_header = header_info.get('parent', [])
        category_header = header_info.get('category', [])
        component_header = header_info.get('component', [])

        processed_frames_data = []
        ordered_unique_marker_identifiers = []
        seen_marker_identifiers = set()

        for index, row in raw_df.iterrows():
            frame_number = row.get(TimeCols.FRAME, str(index))
            time_value = row.get(TimeCols.TIME, "0.0")

            current_frame_output_dict = {'FrameNumber': frame_number, 'Time': time_value}

            min_len = min(len(type_header), len(name_header),
                          len(parent_header), len(category_header),
                          len(component_header), len(row))

            for i in range(min_len - 2):
                current_type = type_header[i]
                current_parent = parent_header[i]
                full_marker_name = name_header[i]

                is_target_marker_x = (
                        current_type == "Rigid Body Marker" and
                        current_parent and
                        ':' in full_marker_name and
                        category_header[i] == "Position" and
                        component_header[i].upper() == 'X'
                )

                if is_target_marker_x:
                    is_y_component_valid = (
                            category_header[i + 1] == "Position" and
                            component_header[i + 1].upper() == 'Y'
                    )
                    is_z_component_valid = (
                            category_header[i + 2] == "Position" and
                            component_header[i + 2].upper() == 'Z'
                    )

                    if is_y_component_valid and is_z_component_valid:
                        name_parts = full_marker_name.split(':', 1)
                        if len(name_parts) < 2 or not name_parts[1]:
                            continue

                        marker_identifier = name_parts[1].replace(" ", "_")

                        prefix_for_face = ""
                        if marker_identifier.startswith("FA"):
                            prefix_for_face = "FA"
                        elif marker_identifier.startswith("BA"):
                            prefix_for_face = "BA"
                        elif marker_identifier:
                            prefix_for_face = marker_identifier[0]

                        face_info = self.face_prefix_map.get(prefix_for_face.upper(), "")

                        x_val = row.iloc[i]
                        y_val = row.iloc[i+1]
                        z_val = row.iloc[i+2]

                        if not x_val or not y_val or not z_val:
                            continue

                        col_face_name = f"{marker_identifier}_FaceInfo"
                        col_x_name = f"{marker_identifier}_X"
                        col_y_name = f"{marker_identifier}_Y"
                        col_z_name = f"{marker_identifier}_Z"

                        if marker_identifier not in seen_marker_identifiers:
                            ordered_unique_marker_identifiers.append(marker_identifier)
                            seen_marker_identifiers.add(marker_identifier)

                        current_frame_output_dict[col_face_name] = face_info
                        current_frame_output_dict[col_x_name] = x_val
                        current_frame_output_dict[col_y_name] = y_val
                        current_frame_output_dict[col_z_name] = z_val

            if len(current_frame_output_dict) > 2: # Has more than just Frame and Time
                processed_frames_data.append(current_frame_output_dict)

        if not processed_frames_data:
            return pd.DataFrame()

        final_output_headers = ['FrameNumber', 'Time']
        ordered_unique_marker_identifiers.sort()
        for marker_id in ordered_unique_marker_identifiers:
            final_output_headers.extend([
                f"{marker_id}_FaceInfo",
                f"{marker_id}_X",
                f"{marker_id}_Y",
                f"{marker_id}_Z"
            ])

        final_df = pd.DataFrame(processed_frames_data, columns=final_output_headers)
        final_df.set_index('Time', inplace=True)
        return final_df
