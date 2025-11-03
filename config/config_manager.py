# flake8: noqa
"""
配置管理模块
Configuration Manager Module
"""

import configparser
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: str = None):
        # 如果没有指定配置文件路径，自动查找项目根目录下的config.ini
        if config_file is None:
            # 尝试从当前工作目录向上查找项目根目录
            current_dir = Path.cwd()
            config_file = self._find_config_file(current_dir)
        
        self.config_file = Path(config_file)
        self.config = configparser.ConfigParser()
        self._config_data = {}
        
        # 同步加载配置
        self._load_config_sync()

    def _find_config_file(self, start_dir: Path) -> str:
        """从指定目录开始向上查找配置文件"""
        current_dir = start_dir
        
        # 最多向上查找5层目录
        for _ in range(5):
            config_path = current_dir / "config" / "config.ini"
            if config_path.exists():
                return str(config_path)
            
            # 如果到达根目录，停止查找
            if current_dir.parent == current_dir:
                break
                
            current_dir = current_dir.parent
        
        # 如果没找到，返回默认路径
        return "config/config.ini"

    async def load_config(self) -> None:
        """异步加载配置文件"""
        self._load_config_sync()
    
    def _load_config_sync(self) -> None:
        """同步加载配置文件"""
        try:
            if not self.config_file.exists():
                raise FileNotFoundError(f"配置文件不存在: {self.config_file}")

            # 保持键的原始大小写
            self.config.optionxform = str

            # 读取配置文件，指定编码为utf-8
            self.config.read(self.config_file, encoding='utf-8')

            # 将配置转换为字典格式便于使用
            self._parse_config()

            logger.info(f"配置文件加载成功: {self.config_file}")

        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            raise

    def _parse_config(self) -> None:
        """解析配置文件"""
        for section_name in self.config.sections():
            self._config_data[section_name] = {}
            for key, value in self.config.items(section_name):
                # 尝试转换数据类型
                self._config_data[section_name][key] = self._convert_value(value)

    def _convert_value(self, value: str) -> Any:
        """转换配置值的数据类型"""
        # 去除首尾空格和注释
        value = value.strip()

        # 处理行内注释（分号或井号）
        if ';' in value:
            value = value.split(';')[0].strip()
        if '#' in value:
            value = value.split('#')[0].strip()

        # 布尔值转换
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'

        # 十六进制转换
        if value.lower().startswith('0x'):
            try:
                return int(value, 16)
            except ValueError:
                pass

        # 数字转换
        try:
            # 尝试转换为整数
            if '.' not in value:
                return int(value)
            # 尝试转换为浮点数
            return float(value)
        except ValueError:
            pass

        # 返回字符串
        return value

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取配置值"""
        try:
            return self._config_data.get(section, {}).get(key, default)
        except Exception:
            return default

    def get_section(self, section: str) -> Dict[str, Any]:
        """获取整个配置段"""
        return self._config_data.get(section, {})

    def get_device_info(self) -> Dict[str, Any]:
        """获取设备信息"""
        return self.get_section("设备配置")

    def get_websocket_config(self) -> Dict[str, Any]:
        """获取WebSocket配置"""
        return self.get_section("Web Socket配置")

    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        # 获取基础数据库配置
        db_config = self.get_section("数据库配置")
        
        # 获取数据库备份配置
        backup_config = self.get_section("数据库备份配置")
        
        # 获取数据库性能配置
        performance_config = self.get_section("数据库性能配置")
        
        # 合并所有数据库相关配置
        merged_config = {}
        merged_config.update(db_config)
        merged_config.update(backup_config)
        merged_config.update(performance_config)
        
        return merged_config

    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self.get_section("服务器配置")

    def get_scada_serial_config(self) -> Dict[str, Any]:
        """获取SCADA串口配置"""
        return self.get_section("SCADA串口配置")

    def get_hmi_serial_config(self) -> Dict[str, Any]:
        """获取HMI串口配置"""
        return self.get_section("HMI串口配置")

    def get_ui_labels_config(self) -> Dict[str, Any]:
        """获取界面标签配置"""
        return self.get_section("界面标签配置")

    def get_image_display_config(self) -> Dict[str, Any]:
        """获取图片显示配置"""
        return self.get_section("图片显示配置")

    def get_system_status_bits(self) -> Dict[str, str]:
        """获取系统状态位配置"""
        return self.get_section("HMI系统状态点表")

    def get_input_bits(self) -> Dict[str, str]:
        """获取开关量输入位配置"""
        return self.get_section("HMI开关量输入点表")

    def get_output_bits(self) -> Dict[str, str]:
        """获取开关量输出位配置"""
        return self.get_section("HMI开关量输出点表")

    def get_fault_bits(self) -> Dict[str, str]:
        """获取故障位配置"""
        return self.get_section("HMI故障点表")

    def get_alarm_bits(self) -> Dict[str, str]:
        """获取报警位配置"""
        return self.get_section("HMI报警点表")

    def get_control_parameters_mapping(self) -> Dict[str, str]:
        """获取控制参数地址映射"""
        return self.get_section("HMI系统控制参数地址映射")

    def get_analog_parameters_mapping(self) -> list:
        """获取模拟量参数映射配置"""
        analog_section = self.get_section("HMI模拟量参数映射")
        analog_mapping = []
        
        # 按寄存器地址排序
        sorted_items = sorted(analog_section.items())
        
        for reg_addr, config_str in sorted_items:
            # 跳过注释和空值
            if not config_str or config_str.strip().startswith('#'):
                continue
                
            # 解析配置字符串：参数名称,单位,转换系数
            parts = [part.strip() for part in config_str.split(',')]
            if len(parts) >= 2:
                name = parts[0]
                unit = parts[1] if len(parts) > 1 else ""
                scale = float(parts[2]) if len(parts) > 2 else 10.0
                
                analog_mapping.append({
                    "reg_addr": reg_addr,
                    "name": name,
                    "unit": unit,
                    "scale": scale
                })
        
        return analog_mapping

    def get_fault_record_config(self) -> Dict[str, Any]:
        """获取故障录波配置"""
        return self.get_section("HMI故障录波读取配置")

    def is_page_enabled(self, page_key: str) -> bool:
        """检查页面是否启用"""
        ui_config = self.get_ui_labels_config()
        return ui_config.get(page_key, True)  # 默认启用

    def get_enabled_pages(self) -> Dict[str, bool]:
        """获取所有启用的页面"""
        ui_config = self.get_ui_labels_config()
        pages = {
            'show_main_diagram': '主接线图',
            'show_system_status': '系统状态',
            'show_event_record': '事件记录',
            'show_real_time_curve': '实时曲线',
            'show_history_curve': '历史曲线',
            'show_parameter_settings': '参数设置',
            'show_api_status': 'API状态',
            'show_fault_record': '故障录波',
            'show_range_settings': '量程设置',
            'show_channel_calibration': '通道校正',
            'show_user_management': '用户管理'
        }

        enabled_pages = {}
        for key, name in pages.items():
            if ui_config.get(key, True):  # 默认启用
                enabled_pages[key] = name

        return enabled_pages

    def get_font_config(self) -> Dict[str, Any]:
        """获取字体配置"""
        return self.get_section("字体配置")

    def get_layout_config(self) -> Dict[str, Any]:
        """获取界面布局配置"""
        return self.get_section("界面布局配置")

    def get_fault_code_mapping(self) -> Dict[str, str]:
        """获取故障码映射配置"""
        return self.get_section("HMI故障点表")

    def reload_config(self) -> None:
        """重新加载配置文件"""
        self._config_data.clear()
        self.load_config()
        logger.info("配置文件已重新加载")