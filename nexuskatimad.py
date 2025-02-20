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
    """
    특정 명령어(또는 명령어 리스트)를 실행시키는 함수.
    shell=True 로 설정 시, 문자열로 입력받은 명령어 전체를 쉘에서 실행 가능.
    """
    subprocess.run(cmd_list, shell=shell, check=True)

def setup_swap():
    """
    10GB 스왑 파일을 생성하고 /etc/fstab에 등록한다.
    이미 설정되어 있으면 건너뛴다.
    """
    # /swapfile이 이미 존재하는지 확인
    swapfile_path = "/swapfile"
    if not os.path.exists(swapfile_path):
        print("[스왑 설정] /swapfile이 없으므로 새로 생성 중...")
        run_command(["sudo", "fallocate", "-l", "10G", swapfile_path])
        run_command(["sudo", "chmod", "600", swapfile_path])
        run_command(["sudo", "mkswap", swapfile_path])
        run_command(["sudo", "swapon", swapfile_path])
    else:
        print("[스왑 설정] /swapfile이 이미 존재함.")

    # /etc/fstab에 스왑 설정이 있는지 확인 후 없으면 추가
    fstab_line = "/swapfile swap swap defaults 0 0"
    try:
        with open("/etc/fstab", "r") as f:
            fstab_content = f.read()
            if fstab_line not in fstab_content:
                print("[스왑 설정] /etc/fstab에 스왑 항목이 없어 추가.")
                run_command(f"echo '{fstab_line}' | sudo tee -a /etc/fstab", shell=True)
            else:
                print("[스왑 설정] /etc/fstab에 이미 스왑 설정이 존재.")
    except FileNotFoundError:
        print("[스왑 설정] /etc/fstab 파일이 없어서 생성 후 추가.")
        run_command(f"echo '{fstab_line}' | sudo tee -a /etc/fstab", shell=True)

    # 설정 결과 확인
    run_command(["sudo", "swapon", "--show"])
    print("[스왑 설정] 10GB 스왑 설정 완료.\n")

def install_prerequisites():
    """
    사전 준비(apt 패키지 업데이트/업그레이드, Rust, protoc 등 설치)
    """
    print("[1단계] apt 업그레이드 진행")
    run_command([
        "sudo", "bash", "-c",
        "DEBIAN_FRONTEND=noninteractive apt-get update && "
        "DEBIAN_FRONTEND=noninteractive apt-get -y "
        "-o Dpkg::Options::='--force-confdef' "
        "-o Dpkg::Options::='--force-confold' "
        "upgrade"
    ])

    print("[2단계] 필수 패키지 설치")
    run_command([
        "sudo", "apt-get", "install", "-y",
        "build-essential", "pkg-config", "libssl-dev",
        "git-all", "curl", "screen", "unzip", "protobuf-compiler"
    ])

    print("[3단계] Rust 설치 (rustup)")
    run_command('curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y', shell=True)

    # 설치된 cargo 버전을 확인하여 정상 설치 확인
    cargo_env = os.path.expanduser("~/.cargo/env")
    if os.path.isfile(cargo_env):
        run_command(f"bash -c 'source {cargo_env} && cargo --version'", shell=True)

    print("[4단계] RISC-V 타겟 추가")
    run_command(f"bash -c 'source {cargo_env} && rustup target add riscv32i-unknown-none-elf'", shell=True)

    print("[5단계] protoc 수동 설치")
    run_command("wget https://github.com/protocolbuffers/protobuf/releases/download/v25.6/protoc-25.6-linux-x86_64.zip", shell=True)
    run_command(["unzip", "-o", "protoc-25.6-linux-x86_64.zip"])
    run_command(["sudo", "mv", "bin/protoc", "/usr/local/bin"])

def send_to_screen(text):
    """
    screen 세션 내에 명령어(또는 답변)을 입력(전송)하는 함수.
    """
    command = text + "\n"
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "stuff", command])

def setup_screen_session():
    """
    백그라운드에서 동작할 screen 세션을 만들고, 로그 설정을 진행하는 함수.
    """
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
    buffer = ""

    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while True:
            new_data = f.read()
            if new_data:
                buffer += new_data

                account_prompt = "Do you want to use the existing user account? (y/n)"
                if account_prompt in buffer:
                    print("기존 사용자 계정 사용 프롬프트 감지됨 → 'y' 전송")
                    send_to_screen("y")
                    buffer = buffer.split(account_prompt, 1)[1]

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        print("로그:", line)
                        for prompt, response in prompts_remaining[:]:
                            if prompt in line:
                                print(f"'{prompt}' 감지됨 → '{response}' 전송")
                                send_to_screen(response)
                                prompts_remaining.remove((prompt, response))
                                break

                    if len(prompts_remaining) == 0:
                        print("모든 자동 응답 완료. 이제 파이썬 스크립트를 종료합니다.")
                        return
            else:
                time.sleep(0.2)

def main():
    # 가장 먼저 스왑 메모리 설정
    setup_swap()

    # 이후 필수 패키지 설치
    install_prerequisites()
    setup_screen_session()

    print("사전 준비가 완료되었습니다. 이제 Nexus CLI 설치를 진행합니다.")
    send_to_screen("curl https://cli.nexus.xyz/ | sh")

    monitor_log_and_respond()
    print("텔레그램 카레 카티마드 채널 : https://t.me/katimad")
    print("자동화 스크립트가 종료됩니다. screen -r nexus 로 세션에 접속할 수 있습니다. (종료 시 Ctrl+A+D)")

if __name__ == "__main__":
    main()
