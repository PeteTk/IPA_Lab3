import paramiko
import time
import os

# รายชื่อ IP Management ของอุปกรณ์ (แทนค่า Y ด้วยหมายเลขกลุ่มของคุณ)
GROUP_Y = "1"  # <--- เปลี่ยนเป็นหมายเลขกลุ่มของคุณ
DEVICES = {
    "R0": f"172.31.111.1",
    "S0": f"172.31.111.2",
    "S1": f"172.31.111.3",
    "R1": f"172.31.111.4",
    "R2": f"172.31.111.5",
}

USERNAME = "admin"
PRIVATE_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")

# โหลด Private Key
key = paramiko.RSAKey.from_private_key_file(PRIVATE_KEY_PATH)

def ssh_connect_and_execute(hostname, ip):
    print(f"\n[+] Connecting to {hostname} ({ip})...")
    client = paramiko.SSHClient()
    
    # ข้ามการตรวจสอบ Host Key ชั่วคราว (AutoAddPolicy)
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # เชื่อมต่อโดยใช้ Public/Private Key Authentication (pkey)
        client.connect(
            hostname=ip,
            username=USERNAME,
            pkey=key,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        print(f"  [✓] SSH Login to {hostname} Successful!")

        # ถ้าเป็น R0 ให้ดึง running-configuration เก็บไว้
        if hostname == "R0":
            print("  [*] Fetching running-config for R0...")
            stdin, stdout, stderr = client.exec_command("show running-config")
            
            # ป้องกันปัญหา Paging (คลิก spacebar) โดยสั่ง terminal length 0 ก่อน หรืออ่านตรงๆ
            time.sleep(2)
            output = stdout.read().decode('utf-8')
            
            # บันทึกลงไฟล์
            filename = "R0_running_config.txt"
            with open(filename, "w") as f:
                f.write(output)
            print(f"  [✓] R0 running-config saved to '{filename}'")

        client.close()

    except Exception as e:
        print(f"  [✗] Failed to connect to {hostname} ({ip}): {e}")

if __name__ == "__main__":
    for host, ip_addr in DEVICES.items():
        ssh_connect_and_execute(host, ip_addr)