#!/usr/bin/env python3
import subprocess
import time
import os

# 스크립트 실행 시 노드 아이디를 직접 입력받는다.
print("노드 아이디를 입력해 주세요, 넥서스 홈페지이에 CLI 노드 아이디 받아서 여기 쓰고 엔터 해:")
NODE_ID = input().strip()

# 스크린 세션 이름 및 로그 파일 경로
SCREEN_SESSION = "nexus"
LOG_FILE = "/tmp/nexus_screen.log"

def run_command(cmd_list, shell=False):
    """
    명령어(리스트 또는 문자열)를 실행하는 함수.
    shell=True인 경우 문자열로 전체 명령어를 전달한다.
    """
    subprocess.run(cmd_list, shell=shell, check=True)

def install_prerequisites():
    """
    (B) ~ (C)에 해당하는 사전 준비 단계:
      1) apt 업데이트 & 업그레이드 (자동으로 로컬 설정 파일 유지)
      2) 필수 패키지 설치
      3) Rust 설치 및 RISC-V 타겟 추가
      4) protoc 설치
    """
    print("[단계] apt 업글할께")
    # 로컬 설정 파일을 유지하기 위해 DEBIAN_FRONTEND=noninteractive + --force-confdef, --force-confold 옵션 사용
    run_command([
        "sudo", "bash", "-c",
        "DEBIAN_FRONTEND=noninteractive apt-get update && "
        "DEBIAN_FRONTEND=noninteractive apt-get -y "
        "-o Dpkg::Options::='--force-confdef' "
        "-o Dpkg::Options::='--force-confold' "
        "upgrade"
    ])

    print("[단계] 패키지도 설치 해야해 (build-essential, pkg-config, 등)")
    run_command([
        "sudo", "apt-get", "install", "-y",
        "build-essential", "pkg-config", "libssl-dev",
        "git-all", "curl", "screen", "unzip", "protobuf-compiler"
    ])

    print("[단계] Rust 설치 (rustup)")
    # rustup 설치 진행
    run_command('curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y', shell=True)

    # 설치 후 현재 쉘에 적용하기 위해 .cargo/env 로드
    cargo_env = os.path.expanduser("~/.cargo/env")
    if os.path.isfile(cargo_env):
        run_command(f"bash -c 'source {cargo_env} && cargo --version'", shell=True)

    print("[단계] RISC-V 타겟 추가")
    run_command(f"bash -c 'source {cargo_env} && rustup target add riscv32i-unknown-none-elf'", shell=True)

    print("[단계] protoc 수동 설치")
    run_command("wget https://github.com/protocolbuffers/protobuf/releases/download/v25.6/protoc-25.6-linux-x86_64.zip", shell=True)
    run_command("unzip protoc-25.6-linux-x86_64.zip", shell=True)
    run_command(["sudo", "mv", "bin/protoc", "/usr/local/bin"])

def send_to_screen(text):
    """
    특정 스크린 세션에 명령어(문자열)을 전송한다.
    """
    command = text + "\n"
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "stuff", command])

def setup_screen_session():
    """
    스크린 세션을 생성하고 로그 파일을 설정한다.
    """
    run_command(["screen", "-S", SCREEN_SESSION, "-dm", "bash"])
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "logfile", LOG_FILE])
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "log", "on"])

def monitor_log_and_respond():
    """
    스크린 로그에서 특정 프롬프트를 감지하면 자동 응답을 보낸다.
    """
    prompts_remaining = [
        ("1) Proceed with standard installation", "1"),
        ("Do you agree to the Nexus Beta Terms of Use", "Y"),
        ("[2] Enter '2'", "2"),
        ("Please enter your node ID:", NODE_ID)
    ]

    # 로그 파일 생성 대기
    while not os.path.exists(LOG_FILE):
        time.sleep(0.5)

    print("로그 파일 감시 시작:", LOG_FILE)
    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        # 파일 끝에서부터 감시
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue

            line = line.strip()
            print("로그:", line)

            for prompt, response in prompts_remaining[:]:
                if prompt in line:
                    print(f"'{prompt}' 감지됨 → '{response}' 전송")
                    send_to_screen(response)
                    prompts_remaining.remove((prompt, response))
                    break

            if len(prompts_remaining) == 0:
                print("모든 자동 응답 완료.")
                break

def main():
    # 사전 준비 (필요 패키지 설치, Rust 설치 등)
    install_prerequisites()

    # 스크린 세션 생성
    setup_screen_session()

    print("사전 준비가 완료되었습니다. 이제 Nexus CLI 설치를 진행합니다.")
    send_to_screen("curl https://cli.nexus.xyz/ | sh")

    # 스크린 로그에서 특정 프롬프트를 감지하고 자동 응답
    monitor_log_and_respond()

    print("자동화 스크립트 완료.")
    print("나 카티마드 라고 해 텔레그램 구독해줘. https://t.me/katimad")
    print(f"스크린 세션을 확인하려면 여기 들어가서봐 : screen -r {SCREEN_SESSION}")

if __name__ == "__main__":
    main()
