# C 语言编码规范（LLM 代码生成约束）

本文档定义了 AI 生成 C 代码时必须遵守的编码规范。所有通过 LLM 生成的代码必须严格遵循本规范。

---

## 1. 文件结构

### 1.1 头文件保护
```c
#ifndef MODULE_NAME_H
#define MODULE_NAME_H

/* 头文件内容 */

#endif /* MODULE_NAME_H */
```

### 1.2 包含顺序
```c
/* 1. 对应的头文件 */
#include "self.h"

/* 2. C 标准库 */
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* 3. 平台/第三方库 */
#include "third_party.h"
```

### 1.3 文件头注释
```c
/**
 * @file    filename.c
 * @brief   简要描述
 * @details 详细描述（可选）
 * @author  Auto-Generated
 * @date    YYYY-MM-DD
 */
```

---

## 2. 命名规范

### 2.1 类型命名
- **结构体**: `PascalCase_t` — 如 `SensorDataV2_t`, `DeviceConfig_t`
- **枚举**: `PascalCase_e` — 如 `WorkMode_e`, `ErrorCode_e`
- **typedef**: 与原类型一致，加 `_t` / `_e` 后缀

### 2.2 函数命名
- **转换函数**: `convert_<Source>_to_<Target>` — 如 `convert_SensorData_to_SensorDataV2`
- **工具函数**: `模块_动作` — 如 `utils_validate_pointer`
- **全小写 + 下划线分隔** — 如 `get_sensor_temperature`

### 2.3 变量命名
- **局部变量**: `snake_case` — 如 `sensor_id`, `temp_value`
- **全局变量**: `g_module_varname` — 如 `g_sensor_current_data`
- **常量/宏**: `MODULE_NAME_VALUE` — 如 `MAX_SENSOR_COUNT`
- **指针变量**: `p_` 前缀 — 如 `p_src`, `p_dst`

### 2.4 枚举值命名
```c
typedef enum {
    MODE_LOW_POWER  = 0,    /* 低功耗模式 */
    MODE_NORMAL     = 1,    /* 正常模式 */
    MODE_HIGH_PERF  = 2,    /* 高性能模式 */
    MODE_COUNT             /* 模式总数，必须放在最后 */
} WorkMode_e;
```

---

## 3. 函数规范

### 3.1 函数签名
```c
/**
 * @brief  函数功能简述
 * @param  src   源数据指针，不可为 NULL
 * @param  dst   目标数据指针，不可为 NULL
 * @return 0 成功，-1 失败
 */
int convert_SensorData_to_SensorDataV2(const SensorData_t *src,
                                        SensorDataV2_t *dst)
{
    /* 函数体 */
}
```

### 3.2 函数设计原则
- **单一职责**: 每个函数只做一件事
- **最大行数**: 不超过 80 行（不含注释和空行）
- **最大参数**: 不超过 5 个参数
- **返回值**: 成功返回 `0`，失败返回 `-1` 或错误码

### 3.3 空指针检查（必须）
```c
int my_function(const Input_t *p_in, Output_t *p_out)
{
    if ((p_in == NULL) || (p_out == NULL)) {
        return -1;
    }
    /* 正常逻辑 */
}
```

---

## 4. 变量规范

### 4.1 声明位置
- **C99/C11**: 允许在块首声明后使用前声明，但**推荐集中在函数开头**
- **C89**: 必须在块首声明

### 4.2 初始化
```c
int ret           = 0;
uint32_t counter  = 0u;
float temperature = 0.0f;
void *p_buf       = NULL;
```

### 4.3 类型使用
| 场景 | 推荐类型 | 避免 |
|------|---------|------|
| 整数 | `int32_t`, `uint32_t`, `int64_t`, `uint64_t` | `int`, `long`, `unsigned` |
| 浮点 | `float`, `double` | — |
| 布尔 | `bool` (需 `<stdbool.h>`) | `int` |
| 字节 | `uint8_t` | `char`, `unsigned char` |
| 大小 | `size_t` | `int` |

---

## 5. 注释规范

### 5.1 文件头注释
```c
/**
 * @file    converter.c
 * @brief   数据结构转换函数集
 */
```

### 5.2 函数注释（Doxygen 风格）
```c
/**
 * @brief  将旧版传感器数据转换为新版
 * @param  p_src  旧版数据指针
 * @param  p_dst  新版数据指针
 * @return 0 成功，-1 参数错误
 * @note   温度从 x100 整数转换为浮点
 */
```

### 5.3 行内注释
```c
/* 温度值除以 100 转换为浮点摄氏度 */
dst->temperature = (float)src->temperature_x100 * 0.01f;
```

### 5.4 注释规则
- **只注释 *为什么*，不注释 *是什么***（代码本身说明是什么）
- 注释与代码同步更新，过期注释比没注释更糟
- 行尾注释用 `/* */`，不用 `//`（保持 C89 兼容）

---

## 6. 控制流规范

### 6.1 if/else
```c
if (condition) {
    /* 分支1 */
} else if (other_condition) {
    /* 分支2 */
} else {
    /* 默认分支 */
}
```
- **必须有 else 分支**（即使为空，也用注释标注意图）
- **禁止省略花括号**，即使只有一行

### 6.2 switch
```c
switch (mode) {
    case MODE_LOW_POWER:
        /* 处理 */
        break;
    case MODE_NORMAL:
        /* 处理 */
        break;
    default:
        /* 必须有 default */
        break;
}
```

### 6.3 循环
```c
/* 明确循环次数时用 for */
for (i = 0u; i < count; i++) {
    /* 循环体 */
}

/* 条件循环用 while */
while (is_running && (retry_count < MAX_RETRY)) {
    /* 循环体 */
    retry_count++;
}
```
- **禁止 `for(;;)` 无限循环**，用 `while(true)` 并注释退出条件
- **禁止在循环体内修改循环变量**

---

## 7. 内存与字符串安全

### 7.1 字符串操作
```c
/* ✅ 推荐：使用带长度限制的函数 */
strncpy(dst->name, src->name, sizeof(dst->name) - 1u);
dst->name[sizeof(dst->name) - 1u] = '\0';

/* ❌ 禁止 */
strcpy(dst->name, src->name);       /* 无边界检查 */
sprintf(buf, "%s", str);            /* 无边界检查 */
```

### 7.2 内存操作
```c
/* 清零结构体 */
memset(&new_data, 0, sizeof(new_data));

/* 复制内存 */
memcpy(p_dst, p_src, copy_size);
```

### 7.3 安全原则
- 所有数组访问必须有边界检查
- `malloc` 必须检查返回值
- `free` 后必须置 `NULL`
- 禁止使用 `gets()`, `scanf("%s", ...)` 等不安全函数

---

## 8. 错误处理

### 8.1 统一模式
```c
int do_something(const Input_t *p_in, Output_t *p_out)
{
    int ret = 0;

    if ((p_in == NULL) || (p_out == NULL)) {
        ret = -1;
    }

    if (ret == 0) {
        /* 步骤1 */
        if (step1_failed) {
            ret = -2;
        }
    }

    if (ret == 0) {
        /* 步骤2 */
        if (step2_failed) {
            ret = -3;
        }
    }

    return ret;
}
```

### 8.2 禁止事项
- **禁止 `assert` 用于运行时错误**（仅用于开发期断言）
- **禁止忽略错误返回值**
- **禁止使用 `goto`**（除统一错误清理外）

---

## 9. 预处理规范

### 9.1 宏定义
```c
/* 常量宏 */
#define MAX_SENSOR_COUNT    (16u)
#define TEMP_SCALE_FACTOR   (0.01f)

/* 函数宏（尽量用内联函数替代） */
#define CLAMP(val, min, max) \
    (((val) < (min)) ? (min) : (((val) > (max)) ? (max) : (val)))
```

### 9.2 条件编译
```c
#ifdef PLATFORM_WINDOWS
    /* Windows 专用代码 */
#elif defined(PLATFORM_LINUX)
    /* Linux 专用代码 */
#else
    #error "Unsupported platform"
#endif
```

---

## 10. 代码格式

### 10.1 缩进与空格
- **缩进**: 4 个空格，禁止 Tab
- **运算符两侧加空格**: `a + b`, `x = y`
- **逗号后加空格**: `func(a, b, c)`
- **指针星号靠类型**: `int *p_var`

### 10.2 花括号
```c
/* ✅ K&R 风格（推荐） */
int func(void) {
    if (condition) {
        /* ... */
    }
}

/* 也允许 Allman 风格 */
int func(void)
{
    if (condition)
    {
        /* ... */
    }
}
```

### 10.3 行宽
- **最大行宽**: 100 字符
- **超长行**: 在运算符后换行，缩进对齐

```c
dst->result = (float)src->value_a * SCALE_A
            + (float)src->value_b * SCALE_B
            + offset;
```

### 10.4 空行
- 函数之间空 **2 行**
- 函数内逻辑块之间空 **1 行**
- 不超过 2 个连续空行

---

## 11. 转换函数专用规范

### 11.1 函数模板
```c
/**
 * @brief  将 <Source> 转换为 <Target>
 * @param  p_src  源结构体指针，不可为 NULL
 * @param  p_dst  目标结构体指针，不可为 NULL
 * @return 0 成功，-1 参数错误
 */
int convert_<Source>_to_<Target>(const <Source>_t *p_src,
                                  <Target>_t *p_dst)
{
    if ((p_src == NULL) || (p_dst == NULL)) {
        return -1;
    }

    /* 1. 直接赋值字段 */
    p_dst->direct_field = p_src->direct_field;

    /* 2. 类型转换字段 */
    p_dst->typed_field = (TargetType)p_src->typed_field;

    /* 3. 缩放转换字段 */
    p_dst->scaled_field = (float)p_src->scaled_field * SCALE_FACTOR;

    /* 4. 字符串拷贝 */
    strncpy(p_dst->name, p_src->name, sizeof(p_dst->name) - 1u);
    p_dst->name[sizeof(p_dst->name) - 1u] = '\0';

    /* 5. 新增字段默认值 */
    p_dst->new_field = DEFAULT_VALUE;
    memset(p_dst->reserved, 0, sizeof(p_dst->reserved));

    return 0;
}
```

### 11.2 编译检查清单
- [ ] 所有指针参数有 NULL 检查
- [ ] 字符串拷贝使用 `strncpy` + 手动 `\0`
- [ ] 整数→浮点转换有显式 `(float)` 强转
- [ ] 缩放系数使用 `f` 后缀（如 `0.01f`）
- [ ] 新增字段有合理默认值
- [ ] `reserved` 字段清零
- [ ] 函数可独立编译，无外部状态依赖
