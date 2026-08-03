from netmiko import ConnectHandler
import re

# ==========================================
# 1. เตรียม Regular Expression (Regex)
# ==========================================
# Regex สำหรับจับชื่อ Interface ที่มีสถานะ "up" และ Protocol "up"
# อธิบาย: จับกลุ่มคำแรก (ชื่อ interface) ที่ตามด้วย IP, YES/NO, Method, และลงท้ายด้วย up up
regex_active_intf = re.compile(r"^([A-Za-z0-9/]+)\s+(?:\S+)\s+(?:\w+)\s+(?:\w+)\s+up\s+up", re.MULTILINE)

# Regex สำหรับจับ Uptime จากคำสั่ง show version
# อธิบาย: หาคำว่า "uptime is " แล้วจับข้อความที่อยู่ด้านหลังทั้งหมดจนจบประโยค
regex_uptime = re.compile(r"uptime is (.*?)\n")

# ==========================================
# 2. กำหนด Connection ของ R1 และ R2
# ==========================================
base_conn = {
    "device_type": "cisco_ios",
    "username": "admin",
    "use_keys": True,
    "key_file": "/home/devasc/.ssh/id_rsa",
    "global_delay_factor": 4,
    "timeout": 30
}

devices = [
    {**base_conn, "host": "172.31.111.4", "name": "Router 1"},
    {**base_conn, "host": "172.31.111.5", "name": "Router 2"},
]

# ==========================================
# 3. ลูปเชื่อมต่อ ดึงข้อมูล และประมวลผลด้วย Regex
# ==========================================
print("=== Starting Netmiko with Regular Expression ===")

for device in devices:
    device_name = device.pop("name") # ดึงชื่อออกมาใช้แสดงผล
    print(f"\n[+] Connecting to {device_name} ({device['host']})...")
    
    try:
        # เชื่อมต่ออุปกรณ์
        net_connect = ConnectHandler(**device)
        net_connect.enable()
        
        # ดึง Uptime (จาก show version)
        sh_version = net_connect.send_command("show version")
        match_uptime = regex_uptime.search(sh_version)
        uptime = match_uptime.group(1) if match_uptime else "Not Found"
        
        # ดึง Active Interfaces (จาก show ip int brief)
        sh_ip_int_br = net_connect.send_command("show ip interface brief")
        active_interfaces = regex_active_intf.findall(sh_ip_int_br)
        
        # แสดงผล
        print(f"[-] Device: {device_name}")
        print(f"    [*] Uptime: {uptime}")
        if active_interfaces:
            print(f"    [*] Active Interfaces: {', '.join(active_interfaces)}")
        else:
            print(f"    [*] Active Interfaces: None")
            
        net_connect.disconnect()
        
    except Exception as e:
        print(f"[!] Error on {device_name}: {e}")

print("\n=== Regex Extraction Completed ===")