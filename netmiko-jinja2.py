from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
from jinja2 import Environment, FileSystemLoader
import time

# ==========================================
# 1. โหลด Jinja2 Template ทั้ง Router และ Switch
# ==========================================
env = Environment(loader=FileSystemLoader('.'))
router_template = env.get_template('router_template.j2')
switch_template = env.get_template('switch_template.j2')  # เพิ่มโหลด Template ของ Switch

# ==========================================
# 2. ข้อมูลสำหรับอุปกรณ์ทั้งหมด (Data)
# ==========================================
data_s1 = {
    "vlan_id": 101,
    "vlan_name": "Control-Data",
    "uplink_ports": "GigabitEthernet0/1, GigabitEthernet1/1",
    "vty_permit_subnets": [
        {"ip": "172.31.111.0", "wildcard": "0.0.0.15"},
        {"ip": "10.30.6.0", "wildcard": "0.0.0.255"}
    ]
}

data_r1 = {
    "vrf_name": "control-data",
    "ospf_process": 1,
    "ospf_area": 0,
    "is_r2": False,
    "interfaces": [
        {"name": "GigabitEthernet0/1"},
        {"name": "GigabitEthernet0/2"},
        {"name": "loopback 0", "ip": "1.1.1.1", "mask": "255.255.255.255"}
    ]
}

data_r2 = {
    "vrf_name": "control-data",
    "ospf_process": 1,
    "ospf_area": 0,
    "is_r2": True,
    "interfaces": [
        {"name": "GigabitEthernet0/1", "nat": "inside"},
        {"name": "GigabitEthernet0/2", "nat": "inside"},
        {"name": "loopback 0", "ip": "2.2.2.2", "mask": "255.255.255.255"}
    ]
}

# ==========================================
# 3. เรนเดอร์ (ผสม) แม่พิมพ์กับข้อมูลเข้าด้วยกัน
# ==========================================
commands_s1 = [cmd.strip() for cmd in switch_template.render(data_s1).splitlines() if cmd.strip()]
commands_r1 = [cmd.strip() for cmd in router_template.render(data_r1).splitlines() if cmd.strip() and not cmd.startswith('!')]
commands_r2 = [cmd.strip() for cmd in router_template.render(data_r2).splitlines() if cmd.strip() and not cmd.startswith('!')]

# เพิ่มคำสั่ง DHCP ให้ G0/3 ของ R2
commands_r2.extend([
    "interface GigabitEthernet0/3",
    "no shutdown",
    "ip address dhcp",
    "ip nat outside",
    "exit",
    "access-list 1 permit any",
    "ip nat inside source list 1 interface GigabitEthernet0/3 vrf control-data overload"
])

# ==========================================
# 4. ข้อมูลการเชื่อมต่อ Netmiko
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
    ({**base_conn, "host": "172.31.111.3", "session_log": "log_s1_j2.txt"}, commands_s1, "Switch 1"),
    ({**base_conn, "host": "172.31.111.4", "session_log": "log_r1_j2.txt"}, commands_r1, "Router 1"),
    ({**base_conn, "host": "172.31.111.5", "session_log": "log_r2_j2.txt"}, commands_r2, "Router 2"),
]

# ==========================================
# 5. ลูปยิงคอนฟิก
# ==========================================
print("=== Starting Netmiko with Jinja2 ===")
for device_info, commands, device_name in devices:
    print(f"\n[+] Connecting to {device_name} ({device_info['host']})...")
    try:
        net_connect = ConnectHandler(**device_info)
        net_connect.enable()
        
        print(f"[*] Sending configurations to {device_name}...")
        output = net_connect.send_config_set(
            commands,
            cmd_verify=False,
            delay_factor=4
        )
        print(output)
        
        net_connect.save_config()
        net_connect.disconnect()
        print(f"[-] Disconnected from {device_name}")
    except Exception as e:
        print(f"[!] Error on {device_name}: {e}")