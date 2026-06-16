/*
 * 测试目标头文件 - 处理后的显示/控制数据
 * 用于 Extern 变量映射工具 v2.1 测试
 * 
 * 场景：HMI 显示系统和控制系统的目标数据结构
 *       源头文件的原始数据经过转换后赋值到这些变量
 */
#ifndef TEST_TARGET_H
#define TEST_TARGET_H

#include <stdint.h>
#include <stdbool.h>

/* ── 温湿度显示数据（转换后） ── */
typedef struct {
    float temperature;             /* 温度 (°C), 从 raw_temperature / 100.0 转换 */
    float humidity;                /* 湿度 (%), 从 raw_humidity / 100.0 转换 */
    float pressure;                /* 气压 (hPa), 直接赋值 */
    bool data_valid;               /* 数据有效标志 */
    uint8_t sensor_id;             /* 传感器编号, 直接赋值 */
    char display_name[32];         /* 显示名称 */
} temp_display_t;

/* ── 电机控制面板数据 ── */
typedef struct {
    float speed_rpm;               /* 转速 (RPM), 直接赋值 */
    float target_rpm;              /* 目标转速 */
    float position_deg;            /* 位置 (度) */
    float target_deg;              /* 目标位置 */
    int32_t torque_nm;             /* 扭矩 (N·m), 从 0.1N·m 转换 */
    uint16_t status;               /* 状态字 */
    uint16_t fault_code;           /* 故障码 */
    uint8_t mode;                  /* 运行模式 */
    bool is_enabled;               /* 使能状态 */
    bool has_fault;                /* 故障标志 */
} motor_panel_t;

/* ── 电池显示数据 ── */
typedef struct {
    float voltage_v;               /* 电压 (V), 从 mV 转换 */
    float current_a;               /* 电流 (A), 从 mA 转换 */
    uint8_t soc_percent;           /* 剩余电量 (%) */
    uint8_t soh_percent;           /* 健康度 (%) */
    float temp_celsius;            /* 温度 (°C), 从 0.1°C 转换 */
    bool is_charging;              /* 充电中 */
    bool is_low_battery;           /* 低电量 */
} battery_display_t;

/* ── 通信状态显示 ── */
typedef struct {
    uint32_t total_packets;        /* 总包数 = tx_count + rx_count */
    uint32_t error_packets;        /* 错误包数 */
    float packet_loss_rate;        /* 丢包率 */
    uint16_t latency_ms;           /* 延迟 (ms), 从 us 转换 */
    bool is_connected;             /* 连接状态 */
} comm_display_t;

/* ── 报警显示数据 ── */
typedef struct {
    bool alarm_active;             /* 有报警激活 */
    uint8_t alarm_count;           /* 激活报警数量 */
    uint8_t max_severity;          /* 最高报警等级 */
    uint32_t alarm_time;           /* 报警时间戳 */
    char alarm_msg[64];            /* 报警消息 */
} alarm_display_t;

/* ── PID 调节面板 ── */
typedef struct {
    float speed_kp;
    float speed_ki;
    float speed_kd;
    float pos_kp;
    float pos_ki;
    float pos_kd;
    uint32_t sample_ms;            /* 采样周期 */
    bool tuning;                   /* 自整定中 */
} pid_panel_t;

/* ── 系统状态面板 ── */
typedef struct {
    uint32_t uptime_s;             /* 运行时间 (秒) */
    float cpu_load;                /* CPU 使用率 (%) */
    bool system_ok;                /* 系统正常 */
    int32_t last_error;            /* 最后错误码 */
    uint8_t dev_id;                /* 设备 ID */
} sys_status_t;

/* ── Extern 变量声明 ── */

/* 温湿度显示 */
extern temp_display_t g_temp_display;

/* 电机面板 */
extern motor_panel_t g_motor1_panel;
extern motor_panel_t g_motor2_panel;

/* 电池显示 */
extern battery_display_t g_battery_display;

/* 通信状态 */
extern comm_display_t g_comm_display;

/* 报警显示 */
extern alarm_display_t g_alarm_display;

/* PID 面板 */
extern pid_panel_t g_pid_panel;

/* 系统状态 */
extern sys_status_t g_sys_status;

/* 基本类型 extern 变量 */
extern uint32_t g_display_update_count;
extern bool g_display_ready;

#endif /* TEST_TARGET_H */
