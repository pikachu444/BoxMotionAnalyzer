import pandas as pd
import csv
import time

class DataLoader:
    def load_csv(self, filepath: str) -> pd.DataFrame:
        """
        CSV 파일을 스트리밍 방식으로 읽고, 필요한 데이터만 선별하여
        메모리 효율적으로 파싱합니다.
        """
        start_time = time.time()
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as infile:
                reader = csv.reader(infile)
                lines = list(reader)
        except FileNotFoundError:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

        if len(lines) < 9:
            raise ValueError("CSV 파일에 헤더 정보가 부족합니다.")

        type_header = [h.strip() for h in lines[2]]
        name_header = [h.strip() for h in lines[3]]
        category_header = [h.strip() for h in lines[6]]

        # 필요한 열의 인덱스와 새 컬럼 이름을 미리 결정합니다.
        columns_to_keep = {} # {original_index: new_name}
        i = 0
        while i < len(type_header):
            obj_type = type_header[i]
            is_target_type = 'Rigid Body' in obj_type or 'Rigid Body Marker' in obj_type
            is_position_data = category_header[i] == 'Position' if i < len(category_header) else False

            if is_target_type and is_position_data:
                obj_name = name_header[i] if i < len(name_header) else ''
                if obj_name:
                    # X, Y, Z 축에 해당하는 인덱스와 새 이름을 저장
                    for axis_idx, axis in enumerate(['X', 'Y', 'Z']):
                        if (i + axis_idx) < len(lines[7]): # 헤더 길이 체크
                             columns_to_keep[i + axis_idx] = f"{obj_name}_{axis}"
                i += 3 # X,Y,Z를 한 그룹으로 보고 3칸 점프
            else:
                i += 1

        processed_data = []
        # 실제 데이터 라인(인덱스 8부터)을 순회합니다.
        for row_data in lines[8:]:
            if not any(row_data) or len(row_data) <= 1: continue

            try:
                frame_time = float(row_data[1])
                frame_dict = {'Time': frame_time}

                # 미리 선별한 열의 데이터만 추출합니다.
                for original_idx, new_name in columns_to_keep.items():
                    if original_idx < len(row_data):
                        try:
                            frame_dict[new_name] = float(row_data[original_idx])
                        except (ValueError):
                            frame_dict[new_name] = None # 숫자로 변환 실패 시 None 처리

                processed_data.append(frame_dict)
            except (ValueError, IndexError):
                continue

        if not processed_data:
            return pd.DataFrame()

        df = pd.DataFrame(processed_data)
        df.set_index('Time', inplace=True)

        end_time = time.time()
        print(f"[DataLoader INFO] CSV parsing time: {end_time - start_time:.4f}s")

        return df

    def get_plottable_targets(self, raw_data: pd.DataFrame) -> list[str]:
        if raw_data is None or raw_data.empty:
            return []

        targets = set()
        for col in raw_data.columns:
            base_name = col.rsplit('_', 1)[0]
            targets.add(base_name)

        final_targets = []
        for name in sorted(list(targets)):
            if ':' in name:
                final_targets.append(name)
            else:
                final_targets.append(f"{name} (Rigid Body)")

        return final_targets
