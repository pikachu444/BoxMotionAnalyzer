import pandas as pd
import csv

class DataLoader:
    def load_csv(self, filepath: str) -> pd.DataFrame:
        """
        AlignBoxInputGenbyExperiment.py의 로직을 참고하고,
        파일 포맷을 정확히 파악하여 CSV를 파싱합니다.
        """
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as infile:
                reader = csv.reader(infile)
                lines = list(reader)
        except FileNotFoundError:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

        if len(lines) < 9: # 메타데이터 2줄 + 헤더 5줄 + 실제 헤더 1줄 + 데이터 1줄
            raise ValueError("CSV 파일에 헤더 정보가 부족합니다.")

        # 헤더 정보 추출 (csv.reader는 이미 리스트의 리스트로 만들어 줌)
        type_header = [h.strip() for h in lines[2]]
        name_header = [h.strip() for h in lines[3]]
        category_header = [h.strip() for h in lines[6]]

        processed_data = []
        # 실제 데이터는 9번째 줄(인덱스 8)부터 시작합니다.
        for row_data in lines[8:]:
            if not any(row_data): continue

            try:
                frame_time = float(row_data[1]) # Time (Seconds)
            except (ValueError, IndexError):
                continue # 시간 값을 float으로 변환할 수 없으면 해당 행은 건너뜁니다.

            frame_dict = {'Time': frame_time}

            # Position 데이터만 추출
            for i in range(len(row_data)):
                # 헤더 정보가 데이터 길이보다 짧으면 무시
                if i >= len(category_header) or i >= len(type_header) or i >= len(name_header):
                    continue

                obj_type = type_header[i]
                is_target_type = ('Rigid Body' in obj_type or 'Rigid Body Marker' in obj_type)
                is_position_data = (category_header[i] == 'Position')

                if is_target_type and is_position_data:
                    obj_name = name_header[i]
                    if not obj_name: continue

                    # 3개의 축(X, Y, Z) 데이터를 한 번에 처리
                    try:
                        # Position 데이터는 항상 X, Y, Z 세트로 있다고 가정
                        if (i + 2) < len(row_data):
                            x_val = float(row_data[i])
                            y_val = float(row_data[i+1])
                            z_val = float(row_data[i+2])

                            # X, Y, Z 컬럼 이름을 한 번에 추가
                            frame_dict[f"{obj_name}_X"] = x_val
                            frame_dict[f"{obj_name}_Y"] = y_val
                            frame_dict[f"{obj_name}_Z"] = z_val
                    except (ValueError, IndexError):
                        continue

            processed_data.append(frame_dict)

        if not processed_data:
            return pd.DataFrame()

        df = pd.DataFrame(processed_data)
        df.set_index('Time', inplace=True)
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
                final_targets.append(f"{name} (강체 중심)")

        return final_targets
