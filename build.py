import os
import shutil
import subprocess
import sys

def clean_previous_builds(dist_path):
    """지정된 빌드 출력 디렉토리와 임시 파일을 정리합니다."""
    print(f"Cleaning up output directory: {dist_path}...")
    
    # 지정된 출력 디렉토리 삭제
    if os.path.exists(dist_path):
        try:
            shutil.rmtree(dist_path)
            print(f"Removed directory: {dist_path}")
        except Exception as e:
            print(f"Error removing {dist_path}: {e}")

    # build 디렉토리는 PyInstaller가 공유하므로 놔두거나 전체 정리 시에만 삭제
    # 여기서는 build 폴더도 정리 (선택 사항)
    if os.path.exists('build'):
        try:
            shutil.rmtree('build')
            print("Removed build directory")
        except Exception as e:
            print(f"Error removing build: {e}")

    # .spec 파일 삭제
    for file in os.listdir('.'):
        if file.endswith('.spec'):
            try:
                os.remove(file)
                print(f"Removed file: {file}")
            except Exception as e:
                print(f"Error removing {file}: {e}")

def build(mode):
    """PyInstaller를 사용하여 애플리케이션을 빌드합니다."""
    print(f"Starting build process (Mode: {mode})...")
    
    # 모드에 따른 출력 경로 설정
    dist_path = os.path.join('dist', mode)
    
    # 이전 빌드 정리
    clean_previous_builds(dist_path)

    # Determine the absolute path to the entry point
    entry_point = os.path.join('src', 'main.py')

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', 'BoxMotionAnalyzer',
        '--windowed',  # 콘솔 창 숨김
        '--noconfirm', # 덮어쓰기 확인 안 함
        '--clean',     # 캐시 정리
        '--distpath', dist_path, # 출력 경로 지정
        # Add src to python path so imports inside main.py work
        '--paths', 'src',
        entry_point    # 진입점
    ]

    if mode == 'onefile':
        cmd.append('--onefile')
    elif mode == 'onedir':
        cmd.append('--onedir')
    else:
        print(f"Invalid build mode: {mode}")
        return

    print(f"Running command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("Build completed successfully!")
        
        final_artifact = os.path.join(dist_path, 'BoxMotionAnalyzer' + ('.exe' if mode == 'onefile' else ''))
        print(f"Artifact created at: {os.path.abspath(final_artifact)}")
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build.py [onedir|onefile]")
        sys.exit(1)
    
    mode = sys.argv[1]
    if mode not in ['onedir', 'onefile']:
        print("Error: Mode must be 'onedir' or 'onefile'")
        sys.exit(1)

    # clean_previous_builds 호출을 build 함수 내부로 이동함
    build(mode)
