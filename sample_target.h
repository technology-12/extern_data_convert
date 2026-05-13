/*
 * 目标头文件 - 用于测试目标头文件变量功能
 * 包含转换后的变量定义以及 extern 变量声明
 */
#ifndef TARGET_HEADER_H
#define TARGET_HEADER_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    float temperature;
    float humidity;
    double pressure;
    bool valid;
    uint8_t sensor_id;
} target_sensor_t;

typedef struct {
    float speed;
    float position;
    uint16_t status;
    bool enabled;
} target_motor_t;

typedef struct {
    float kp;
    float ki;
    float kd;
} target_pid_t;

extern target_sensor_t g_target_sensor;
extern target_motor_t g_target_motor;
extern target_pid_t g_target_pid;
extern uint32_t g_target_tick;
extern float g_target_voltage;
extern bool g_target_ready;

#endif /* TARGET_HEADER_H */
