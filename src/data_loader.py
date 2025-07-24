import pandas as pd
import csv

class DataLoader:
    def load_csv(self, filepath: str) -> pd.DataFrame:
        """
        AlignBoxInputGenbyExperiment.py의 순수 Python 로직을 사용하여
        CSV를 파싱하고, 최종적으로 Pandas DataFrame을 반환합니다.
        """
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as infile:
                lines = infile.readlines()
        except FileNotFoundError:
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")

        if len(lines) < 8:
            raise ValueError("CSV 파일에 헤더 정보가 부족합니다.")

        # 헤더 정보 추출
        type_header = [h.strip() for h in lines[2].strip().split(',')]
        name_header = [h.strip() for h in lines[3].strip().split(',')]
        category_header = [h.strip() for h in lines[6].strip().split(',')]

        processed_data = []
        # 데이터 라인 처리 (8번째 줄부터 시작)
        for line in lines[8:]:
            if not line.strip(): continue

            row_data = [d.strip() for d in line.split(',')]
            frame_time = row_data[1] # Time (Seconds)

            frame_dict = {'Time': float(frame_time)}

            # Position 데이터만 추출
            for i in range(2, len(row_data) - 2, 3):
                if i >= len(category_header) or i >= len(type_header): continue

                obj_type = type_header[i]
                is_target_type = ('Rigid Body' in obj_type) or ('Rigid Body Marker' in obj_type)
                is_position_data = (category_header[i] == 'Position')

                if is_target_type and is_position_data:
                    obj_name = name_header[i] if i < len(name_header) else ''
                    if not obj_name: continue

                    try:
                        frame_dict[f"{obj_name}_X"] = float(row_data[i])
                        frame_dict[f"{obj_name}_Y"] = float(row_data[i+1])
                        frame_dict[f"{obj_name}_Z"] = float(row_data[i+2])
                    except (ValueError, IndexError):
                        continue # 숫자가 아니거나 인덱스 초과시 무시

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
            # '_X', '_Y', '_Z' 를 제거하여 기본 이름을 얻습니다.
            base_name = col.rsplit('_', 1)[0]
            targets.add(base_name)

        final_targets = []
        for name in sorted(list(targets)):
            if ':' in name:
                final_targets.append(name)
            else:
                final_targets.append(f"{name} (강체 중심)")

        return final_targets
