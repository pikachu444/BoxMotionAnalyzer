# =============================================
#   VTP 시계열 메타파일(.pvd) 생성기
#   (ParaView 타임라인/애니메이션 연동)
# =============================================
# 1. config.py에서 박스/마커 vtp 경로, 프레임 수, fps 등 참조
# 2. 모든 .vtp 파일을 하나의 시계열 데이터로 묶는 .pvd 파일 생성
# =============================================

import config

def make_pvd_entry(filename, time):
    return f'    <DataSet timestep="{time:.6f}" group="" part="0" file="{filename}"/>'

def main():
    n_frames = config.N_FRAMES
    fps = config.FPS

    # 박스/마커 vtp 경로 템플릿
    box_pattern = config.VTP_BOX_PATH
    marker_pattern = config.VTP_MARKER_PATH

    # PVD 헤더
    lines = [
        '<?xml version="1.0"?>',
        '<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">',
        '  <Collection>'
    ]

    # 프레임별로 박스, 마커 각각 시계열로 묶음
    for i in range(n_frames):
        t = i / fps
        boxfile = box_pattern.format(i)
        markerfile = marker_pattern.format(i)
        lines.append(make_pvd_entry(boxfile, t))
        lines.append(make_pvd_entry(markerfile, t))

    # 끝
    lines += [
        '  </Collection>',
        '</VTKFile>'
    ]

    # 파일로 저장
    with open(config.PVD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✓ PVD 파일 생성 완료: {config.PVD_PATH}")

if __name__ == '__main__':
    main()
