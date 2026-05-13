/*
 * 示例头文件 - 用于测试 Extern 变量映射工具
 * 包含多种 extern 变量声明和结构体定义
 */
#ifndef SAMPLE_EXTERN_H
#define SAMPLE_EXTERN_H

#include <stdint.h>
#include <stdbool.h>

/* ── 传感器数据结构体 ── */
typedef struct {
    int32_t temperature;
    float humidity;
    double pressure;
    bool valid;
    uint8_t sensor_id;
    uint16_t raw_adc;
    float calibrated_value;
    char sensor_name[32];
} sensor_data_t;

/* ── 电机控制结构体 ── */
typedef struct {
    float target_speed;
    float current_speed;
    float target_position;
    float current_position;
    uint16_t status_word;
    uint16_t error_code;
    uint8_t mode;
    bool enabled;
    bool fault;
    int32_t torque;
} motor_control_t;

/* ── 系统配置结构体（嵌套） ── */
typedef struct {
    float kp;
    float ki;
    float kd;
    int32_t integral_limit;
    int32_t output_limit;
} pid_params_t;

typedef struct {
    uint8_t node_id;
    uint32_t baudrate;
    uint16_t heartbeat_ms;
    bool enable;
} can_config_t;

typedef struct {
    pid_params_t position_pid;
    pid_params_t speed_pid;
    can_config_t can_bus;
    uint32_t cycle_time_ms;
    char firmware_version[16];
    bool debug_mode;
} system_config_t;

/* ── 简单报警结构体 ── */
typedef struct {
    bool over_temperature;
    bool over_pressure;
    bool communication_error;
    bool motor_fault;
    uint8_t severity_level;
    uint32_t timestamp;
} alarm_status_t;

/* ── Extern 变量声明 ── */

/* 传感器数据 */
extern sensor_data_t g_sensor_data;
extern sensor_data_t g_sensor_data_backup;

/* 电机控制 */
extern motor_control_t g_motor1;
extern motor_control_t g_motor2;

/* 系统配置 */
extern system_config_t g_sys_config;

/* 报警状态 */
extern alarm_status_t g_alarm;

/* 基本类型 extern 变量 */
extern uint32_t g_system_tick;
extern float g_battery_voltage;
extern bool g_system_ready;
extern int32_t g_error_count;
extern const uint8_t g_device_id;

#endif /* SAMPLE_EXTERN_H */
