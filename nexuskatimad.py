#!/usr/bin/env python3
import subprocess
import time
import os

# 스크립트 실행 시 노드 아이디 입력
print("노드 아이디를 입력해 주세요:")
NODE_ID = input().strip()

# 스크린 세션 이름 및 로그 파일 경로
SCREEN_SESSION = "nexus"
LOG_FILE = "/tmp/nexus_screen.log"

def run_command(cmd_list, shell=False):
    subprocess.run(cmd_list, shell=shell, check=True)

def install_prerequisites():
    """
    사전 준비(apt 패키지 업데이트/업그레이드, Rust, protoc 등 설치)
    """
    print("[1단계] apt 업글한다다")
    run_command([
        "sudo", "bash", "-c",
        "DEBIAN_FRONTEND=noninteractive apt-get update && "
        "DEBIAN_FRONTEND=noninteractive apt-get -y "
        "-o Dpkg::Options::='--force-confdef' "
        "-o Dpkg::Options::='--force-confold' "
        "upgrade"
    ])

    print("[2단계] 필수 패키지 설치한다.")
    run_command([
        "sudo", "apt-get", "install", "-y",
        "build-essential", "pkg-config", "libssl-dev",
        "git-all", "curl", "screen", "unzip", "protobuf-compiler"
    ])

    print("[3단계] Rust 설치 (rustup)")
    run_command('curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y', shell=True)

    cargo_env = os.path.expanduser("~/.cargo/env")
    if os.path.isfile(cargo_env):
        run_command(f"bash -c 'source {cargo_env} && cargo --version'", shell=True)

    print("[4단계] RISC-V 타겟 추가")
    run_command(f"bash -c 'source {cargo_env} && rustup target add riscv32i-unknown-none-elf'", shell=True)

    print("[5단계] protoc 수동 설치")
    run_command("wget https://github.com/protocolbuffers/protobuf/releases/download/v25.6/protoc-25.6-linux-x86_64.zip", shell=True)
    run_command("unzip protoc-25.6-linux-x86_64.zip", shell=True)
    run_command(["sudo", "mv", "bin/protoc", "/usr/local/bin"])

def send_to_screen(text):
    command = text + "\n"
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "stuff", command])

def setup_screen_session():
    run_command(["screen", "-S", SCREEN_SESSION, "-dm", "bash"])
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "logfile", LOG_FILE])
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "log", "on"])

def monitor_log_and_respond():
    """
    스크린 로그에서 특정 프롬프트를 감지해 자동으로 응답.
    모든 응답 후 스크립트만 종료하고, 스크린 세션은 계속 유지.
    """
    prompts_remaining = [
        ("1) Proceed with standard installation", "1"),
        ("Do you agree to the Nexus Beta Terms of Use", "Y"),
        ("[2] Enter '2'", "2"),
        ("Please enter your node ID:", NODE_ID)
    ]

    while not os.path.exists(LOG_FILE):
        time.sleep(0.5)

    print("로그 파일 감시 시작:", LOG_FILE)
    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
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
                print("모든 자동 응답 완료. 이제 파이썬 스크립트를 종료합니다.")
                break

def main():
    install_prerequisites()
    setup_screen_session()

    print("사전 준비가 완료되었습니다. 이제 Nexus CLI 설치를 진행합니다.")
    send_to_screen("curl https://cli.nexus.xyz/ | sh")

    monitor_log_and_respond()
    print("텔레그램 카레 카티마드 채널 : https://t.me/katimad ")
    print("자동화 스크립트가 종료됩니다. 자 들어가서 보고싶으면 screen -r nexus 로 세션에 접속해 확인 가능합니다. 빠져나올땐 컨트롤+A+D 를 누르세요")

if name == "main":
    main()