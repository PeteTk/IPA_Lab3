from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
import time

# ==========================================
# 1. ชุดคำสั่งสำหรับแต่ละอุปกรณ์
# ==========================================

commands_s1 = [
    "vlan 101",
    "name Control-Data",
    "exit",
    "interface range GigabitEthernet0/1, GigabitEthernet1/1",
    "switchport mode access",
    "switchport access vlan 101",
    "exit",

    "ip access-list standard VTY_ACCESS",
    "permit 172.31.111.0 0.0.0.15",
    "permit 10.30.6.0 0.0.0.255",
    "exit",

    "line vty 0 4",
    "access-class VTY_ACCESS in",
    "line vty 5 15",
    "access-class VTY_ACCESS in",
    "exit"
]

# ***** จุดแก้ไขหลัก: ต้องสร้าง VRF ก่อน ค่อยอ้างอิงใน OSPF/interface *****
commands_r1 = [
    # 1) สร้าง VRF ก่อนเสมอ ป้องกัน error/หลุด session ตอนสั่ง "router ospf ... vrf ..."
    "ip vrf control-data",
    "exit",

    # ลบ router ospf 1 (global) เดิมทิ้งก่อน เพื่อเอา process-id 1 มาใช้กับ VRF แทน
    # *** ต้องมั่นใจแล้วว่า process นี้ไม่ได้ใช้ดูแลเส้นทางไป management IP ***
    "no router ospf 1",

    "router ospf 1 vrf control-data",
    "exit",

    # 2) ผูก interface เข้า VRF ก่อน แล้วค่อยใส่ ip ospf (สำคัญมาก ถ้าลืมขั้นตอนนี้
    #    OSPF process จะไม่รู้จัก interface และบางรุ่นจะฟ้อง error กลางคัน)
    "interface GigabitEthernet0/1",
    "ip vrf forwarding control-data",
    "ip ospf 1 area 0",
    "exit",
    "interface GigabitEthernet0/2",
    "ip vrf forwarding control-data",
    "ip ospf 1 area 0",
    "exit",
    "interface loopback 0",
    "ip vrf forwarding control-data",
    # ใช้ /32 host route ตาม convention ทั่วไป (ดูตัวอย่างจากสไลด์ netmiko02.py หน้า 28
    # ที่ตั้ง loopback0 เป็น 1.1.1.1/32) — ไม่ชนกับ subnet อื่นในแล็บแน่นอน
    "ip address 1.1.1.1 255.255.255.255",
    "ip ospf 1 area 0",
    "exit",

    "ip access-list standard VTY_ACCESS",
    "permit 172.31.111.0 0.0.0.15",
    "permit 10.30.6.0 0.0.0.255",
    "exit",

    "line vty 0 4",
    "access-class VTY_ACCESS in vrf-also",
    "line vty 5 15",
    "access-class VTY_ACCESS in vrf-also",
    "exit"
]

commands_r2 = [
    "ip vrf control-data",
    "exit",

    # ลบ router ospf 1 (global) เดิมทิ้งก่อน เพื่อเอา process-id 1 มาใช้กับ VRF แทน
    "no router ospf 1",

    "router ospf 1 vrf control-data",
    "default-information originate always",  # ใช้ always กัน OSPF ไม่ยอม advertise
                                               # ถ้า default route จาก DHCP ยังไม่เข้า RIB ตอนนั้น
    "exit",

    "interface GigabitEthernet0/1",
    "ip vrf forwarding control-data",
    "ip ospf 1 area 0",
    "ip nat inside",
    "exit",
    "interface GigabitEthernet0/2",
    "ip vrf forwarding control-data",
    "ip ospf 1 area 0",
    "ip nat inside",
    "exit",
    "interface loopback 0",
    "ip vrf forwarding control-data",
    # ใช้ /32 host route ผูกกับหมายเลข router (2 = R2) ตาม convention เดียวกับ R1
    "ip address 2.2.2.2 255.255.255.255",
    "ip ospf 1 area 0",
    "exit",
    "interface GigabitEthernet0/3",
    "no shutdown",
    "ip address dhcp",
    "ip nat outside",
    "exit",

    # ไม่ใส่ static default route ผ่าน G0/3 แล้ว เพราะเป็น multi-access interface
    # ต้องระบุ next-hop ที่รู้ล่วงหน้าไม่ได้ (มาจาก DHCP) — ปล่อยให้ DHCP client
    # ติดตั้ง default route ให้อัตโนมัติใน VRF control-data แทน
    "access-list 1 permit any",
    "ip nat inside source list 1 interface GigabitEthernet0/3 vrf control-data overload",

    "ip access-list standard VTY_ACCESS",
    "permit 172.31.111.0 0.0.0.15",
    "permit 10.30.6.0 0.0.0.255",
    "exit",

    "line vty 0 4",
    "access-class VTY_ACCESS in vrf-also",
    "line vty 5 15",
    "access-class VTY_ACCESS in vrf-also",
    "exit"
]

# ==========================================
# 2. กำหนดข้อมูลการเชื่อมต่อ (เพิ่ม timeout ให้ทนต่อ device เสมือนที่ CPU ต่ำ)
# ==========================================

base_conn = {
    "device_type": "cisco_ios",
    "username": "admin",
    "use_keys": True,
    "key_file": "/home/devasc/.ssh/id_rsa",
    "global_delay_factor": 4,       # เพิ่มจาก 2 -> 4 ให้รอ CPU ประมวลผลนานขึ้น
    "timeout": 30,                  # พารามิเตอร์นี้มีมาตั้งแต่ Netmiko เวอร์ชันเก่า ๆ ใช้ได้ชัวร์
    "session_log": None,            # จะเซ็ตแยกต่อ device ด้านล่างเพื่อ debug
}

cisco_s1 = {**base_conn, "host": "172.31.111.3", "session_log": "log_s1.txt"}
cisco_r1 = {**base_conn, "host": "172.31.111.4", "session_log": "log_r1.txt"}
cisco_r2 = {**base_conn, "host": "172.31.111.5", "session_log": "log_r2.txt"}

# ==========================================
# 3. จับคู่ข้อมูลอุปกรณ์กับชุดคำสั่ง
# ==========================================

devices = [
    (cisco_s1, commands_s1, "Switch 1"),
    (cisco_r1, commands_r1, "Router 1"),
    (cisco_r2, commands_r2, "Router 2"),
]

# ==========================================
# 4. ลูปยิงคอนฟิกเข้าอุปกรณ์ (ยิงทีละคำสั่ง + retry เพื่อลดผลกระทบถ้า channel หลุด)
# ==========================================

print("=== Starting Network Automation (Netmiko Lab) ===")

for device_info, commands, device_name in devices:
    print(f"\n[+] Connecting to {device_name} ({device_info['host']})...")
    try:
        net_connect = ConnectHandler(**device_info)
        net_connect.enable()

        print(f"[*] Sending configurations to {device_name}...")
        try:
            # ยิงทั้งชุดตามปกติก่อน (เร็วกว่า)
            output = net_connect.send_config_set(
                commands,
                cmd_verify=False,     # ลดปัญหา prompt ไม่ match ระหว่าง VRF interface
                delay_factor=4,       # ใช้ delay_factor แทน read_timeout เพื่อรองรับ Netmiko เวอร์ชันเก่า
            )
            print(output)
        except Exception as e:
            # ถ้าหลุดกลางคัน ให้ลองต่อใหม่แล้วยิงทีละคำสั่งแทน (ช่วย debug ว่าค้างที่บรรทัดไหน)
            print(f"[!] send_config_set ล้มเหลว ({e}) กำลังลองยิงทีละคำสั่ง...")
            net_connect.disconnect()
            net_connect = ConnectHandler(**device_info)
            net_connect.enable()
            net_connect.config_mode()
            error_markers = ["% Invalid input", "does not match", "% Incomplete", "Invalid input detected"]
            for cmd in commands:
                print(f"    -> {cmd}")
                out = net_connect.send_command_timing(cmd, delay_factor=2)
                if out.strip():
                    print(f"       {out.strip()}")
                if any(marker in out for marker in error_markers):
                    print(f"    [!!!] หยุดทันที: คำสั่ง '{cmd}' ทำให้เกิด error บน {device_name}")
                    print(f"          กรุณาตรวจสอบ config ปัจจุบันของอุปกรณ์ก่อนรันซ้ำ (เช่น router ospf id ที่ชนกัน)")
                    break
                time.sleep(0.5)
            net_connect.exit_config_mode()

        net_connect.save_config()
        print(f"[+] Saved configuration on {device_name}")

        net_connect.disconnect()
        print(f"[-] Disconnected from {device_name}")

    except NetmikoAuthenticationException as e:
        print(f"[!] Authentication failed for {device_name}.")
        print(f"    >> สาเหตุ: {e}")
    except NetmikoTimeoutException as e:
        print(f"[!] Connection timed out for {device_name}.")
        print(f"    >> สาเหตุ: {e}")
    except Exception as e:
        print(f"[!] An error occurred on {device_name}: {e}")

print("\n=== Automation Completed ===")