#!/usr/bin/env python3
import subprocess
import time
import os

print("노드 아이디를 입력해 주세요:")
NODE_ID = input().strip()

SCREEN_SESSION = "nexus"
LOG_FILE = "/tmp/nexus_screen.log"

def run_command(cmd_list, shell=False):
    subprocess.run(cmd_list, shell=shell, check=True)

def setup_swap():
    swapfile_path = "/swapfile"
    if not os.path.exists(swapfile_path):
        print("[스왑 설정] /swapfile이 없으므로 새로 생성 중...")
        run_command(["sudo", "fallocate", "-l", "10G", swapfile_path])
        run_command(["sudo", "chmod", "600", swapfile_path])
        run_command(["sudo", "mkswap", swapfile_path])
        run_command(["sudo", "swapon", swapfile_path])
    else:
        print("[스왑 설정] /swapfile이 이미 존재함.")

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

    run_command(["sudo", "swapon", "--show"])
    print("[스왑 설정] 10GB 스왑 설정 완료.\n")

def install_prerequisites():
    print("[1단계] apt 업데이트 & 업그레이드 (로컬 설정 파일 유지)")
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
    command = text + "\n"
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "stuff", command])

def setup_screen_session():
    run_command(["screen", "-S", SCREEN_SESSION, "-dm", "bash"])
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "logfile", LOG_FILE])
    run_command(["screen", "-S", SCREEN_SESSION, "-X", "log", "on"])

def monitor_log_and_respond():
    """
    특정 문자열이 포함되면 자동으로 명령을 입력하도록 사전(dict)을 활용.
    - 하나의 키워드가 여러 번 등장해도 계속 응답하도록 한다.
    """
    # 감지할 키워드와 응답을 매핑
    # 주의: "부분 일치"를 사용하므로, 키워드가 문장 내 일부분만 매칭되어도 응답
    prompts_to_response = {
        "1) Proceed with standard installation": "1",
        "Do you agree to the Nexus Beta Terms of Use": "Y",
        "Do you agree to the Nexus Beta Terms of Use (https://nexus.xyz/terms-of-use)? (Y/n)": "Y",
        "[2] Enter '2' to start earning NEX by connecting adding your node ID": "2",
        "start earning NEX by connecting adding your node ID": "2",
        "Please enter your node ID:": NODE_ID,
        # 계정 사용 여부
        "Do you want to use the existing user account? (y/n)": "y",
    }

    while not os.path.exists(LOG_FILE):
        time.sleep(0.5)

    print("로그 파일 감시 시작:", LOG_FILE)
    buffer = ""

    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        # 처음부터 읽지 않고, 파일 끝으로 이동
        f.seek(0, os.SEEK_END)
        while True:
            new_data = f.read()
            if new_data:
                buffer += new_data

                # 한 줄씩 처리
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line_stripped = line.strip()
                    if line_stripped:
                        print("로그:", line_stripped)

                        # 모든 키워드에 대해 부분 일치를 확인
                        for prompt_substring, response in prompts_to_response.items():
                            if prompt_substring in line_stripped:
                                print(f"→ '{prompt_substring}' 부분 일치. '{response}' 전송")
                                send_to_screen(response)
            else:
                time.sleep(0.2)

def main():
    setup_swap()
    install_prerequisites()
    setup_screen_session()

    print("사전 준비가 완료되었습니다. 이제 Nexus CLI 설치를 진행합니다.")
    send_to_screen("curl https://cli.nexus.xyz/ | sh")

    monitor_log_and_respond()
    print("텔레그램 카레 카티마드 채널 : https://t.me/katimad")
    print("자동화 스크립트가 종료됩니다. 'screen -r nexus'로 접속 가능 (Ctrl+A+D로 분리)")

if __name__ == "__main__":
    main()
