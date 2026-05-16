/*
 * 测试源头文件 - 工业传感器原始数据
 * 用于 Extern 变量映射工具 v2.1 测试
 * 
 * 场景：工业设备数据采集系统，包含原始传感器读数、电机状态、通信数据等
 */
#ifndef TEST_SOURCE_H
#define TEST_SOURCE_H

#include <stdint.h>
#include <stdbool.h>

/* ── 温湿度传感器数据 ── */
typedef struct {
    int32_t raw_temperature;       /* 原始温度值 (0.01°C) */
    uint32_t raw_humidity;         /* 原始湿度值 (0.01%) */
    float pressure;                /* 气压值 (hPa) */
    bool sensor_valid;             /* 传感器数据有效标志 */
    uint8_t sensor_id;             /* 传感器编号 */
    uint16_t adc_value;            /* ADC 采样原始值 */
    char sensor_name[16];          /* 传感器名称 */
} temp_sensor_t;

/* ── 电机运行数据 ── */
typedef struct {
    float speed;                   /* 当前转速 (RPM) */
    float target_speed;            /* 目标转速 */
    float position;                /* 当前位置 (度) */
    float target_position;         /* 目标位置 */
    int32_t torque;                /* 当前扭矩 (0.1 N·m) */
    uint16_t status_word;          /* 状态字 */
    uint16_t error_code;           /* 故障码 */
    uint8_t run_mode;              /* 运行模式: 0=停止 1=速度 2=位置 */
    bool enabled;                  /* 使能状态 */
    bool fault;                    /* 故障标志 */
} motor_status_t;

/* ── 电池管理数据 ── */
typedef struct {
    uint16_t voltage;              /* 电池电压 (mV) */
    int16_t current;               /* 电池电流 (mA, 负值=放电) */
    uint8_t soc;                   /* 剩余电量 (%) */
    uint8_t soh;                   /* 电池健康度 (%) */
    uint16_t temperature;          /* 电池温度 (0.1°C) */
    bool charging;                 /* 充电标志 */
    bool low_battery;              /* 低电量报警 */
} battery_info_t;

/* ── 通信统计 ── */
typedef struct {
    uint32_t tx_count;             /* 发送计数 */
    uint32_t rx_count;             /* 接收计数 */
    uint32_t error_count;          /* 错误计数 */
    uint16_t latency_us;           /* 延迟 (微秒) */
    bool connected;                /* 连接状态 */
} comm_stats_t;

/* ── 系统报警数据 ── */
typedef struct {
    bool over_temperature;         /* 温度过高 */
    bool over_pressure;            /* 压力过高 */
    bool communication_error;      /* 通信故障 */
    bool motor_fault;              /* 电机故障 */
    bool battery_low;              /* 电量不足 */
    uint8_t severity_level;        /* 报警等级 0-5 */
    uint32_t alarm_timestamp;      /* 报警时间戳 */
} alarm_data_t;

/* ── PID 参数（嵌套结构体） ── */
typedef struct {
    float kp;
    float ki;
    float kd;
    int32_t integral_limit;
    int32_t output_limit;
} pid_params_t;

typedef struct {
    pid_params_t speed_pid;        /* 速度环 PID */
    pid_params_t position_pid;     /* 位置环 PID */
    uint32_t sample_time_ms;       /* 采样周期 */
    bool auto_tune;                /* 自整定标志 */
} controller_params_t;

/* ── Extern 变量声明 ── */

/* 温湿度传感器 */
extern temp_sensor_t g_temp_sensor;

/* 电机状态 */
extern motor_status_t g_motor1;
extern motor_status_t g_motor2;

/* 电池信息 */
extern battery_info_t g_battery;

/* 通信统计 */
extern comm_stats_t g_comm;

/* 报警数据 */
extern alarm_data_t g_alarm;

/* 控制器参数 */
extern controller_params_t g_controller;

/* 基本类型 extern 变量 */
extern uint32_t g_system_tick;
extern float g_cpu_usage;
extern bool g_system_ready;
extern int32_t g_error_code;
extern uint8_t g_device_id;

#endif /* TEST_SOURCE_H */
