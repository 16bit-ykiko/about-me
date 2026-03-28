---
title: 为 CuTe DSL 支持 AOT
date: "2025-11-11 21:38:08"
updated: "2026-03-29 04:07:14"
zhihu_article_id: "1971691994037334904"
zhihu_url: https://zhuanlan.zhihu.com/p/1971691994037334904
---

## Why do we need AOT for CuTe DSL?

CUTLASS C++ 是一个用来编写高性能 CUDA 算子的库，以复杂难学著称。为了降低学习成本，NVIDIA 推出了基于 Python 的 [CuTe DSL](https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/overview.html)。使用 Python 而不是 C++ 模板来进行元编程具有很多好处，首先就是用户不必和 C++ 那些晦涩难懂的模板报错作斗争了，这对于 C++ 初学者来说是非常头疼的一件事情，现在他们可以专注于代码逻辑。另外，nvcc 编译很慢，而其中大部分时间是花在编译器前端，也就是解析 C++ 代码上。尤其是对于 CUTLASS 这样 template heavy 的库，主要的时间都花在处理模板实例化上了，使用 CuTe DSL 可以绕过这个问题。相比于使用 CUTLASS 的 C++ 代码，它编译的速度能提升几十甚至上百倍。除此之外，现在算子和单测都可以一起在 Python 里写了，也方便了很多。

使用 Python 来编写原型是很好的，但是在部署推理服务时，我们希望依赖尽可能简单，像 Python 那样要装一大堆随时可能因为版本问题导致崩溃的依赖就不好了。如果能把使用 CuTe DSL 编写的算子编译成 library 供 C++ 代码调用就好了。这正是我们想要为 CuTe DSL 支持 AOT 的目的。

## Export Binary

CuTe DSL 在 [v4.3](https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/cute_dsl_general/debugging.html) 添加了导出编译好的 kernel 对应的 ptx 和 cubin 的选项。设置下面几个环境变量即可

```bash
export CUTE_DSL_KEEP_PTX=1
export CUTE_DSL_KEEP_CUBIN=1
export CUTE_DSL_DUMP_DIR=/tmp
```

直接访问 kernel 对应的 `__ptx__` 或者 `__cubin__` 属性，即可获取对应的值：

```python
compiled_foo = cute.compile(foo, ...)
print(f"PTX: {compiled_foo.__ptx__}")
with open("foo.cubin", "wb") as f:
    f.write(compiled_foo.__cubin__)
```

所以现在我们有了算子对应的 cubin 文件，剩下的问题就是：

1. 如何在 C++ 代码中加载 cubin 格式的算子
2. 如何把 cubin 文件嵌入到 C++ 代码中一起编译成 library
3. 生成 h 头文件供下游用户调用

## CUDA Driver API

对于问题 1，我们可以调用 [CUDA Driver API](https://docs.nvidia.com/cuda/cuda-driver-api/index.html) 来实现。

```cpp
CUresult CUDAAPI cuModuleLoadData(CUmodule *module, const void *image);
CUresult CUDAAPI cuModuleGetFunction(CUfunction *hfunc, CUmodule hmod, const char *name);
```

通过 `cuModuleLoadData` 加载 cubin 文件，`cuModuleGetFunction` 获取其中的 kernel 函数

```cpp
CUresult CUDAAPI cuLaunchKernel(CUfunction f,
                                unsigned int gridDimX,
                                unsigned int gridDimY,
                                unsigned int gridDimZ,
                                unsigned int blockDimX,
                                unsigned int blockDimY,
                                unsigned int blockDimZ,
                                unsigned int sharedMemBytes,
                                CUstream hStream,
                                void **kernelParams,
                                void **extra);
```

再通过 `cuLaunchKernel` 启动这个 kernel 即可，值得注意的点是 kernel 参数都通过 `void**` 也就是 `void*` 数组传递，也就是我们需要知道 kernel 的函数签名，才能启动 kernel。

## Embed Binary

对于问题 2，我们需要某种将二进制文件嵌入到 C++ 文件中的手段，然后直接在 C++ 文件中引用这个 kernel 即可。关于如何在 C++ 代码中嵌入二进制文件的讨论也值得单开一个文章进行介绍了，这里不过多展开。只说一下我这里选用的方法。使用 `objcopy` 将二进制文件变成 ELF 格式的文件，同时会在其中插入几个符号用于引用二进制数据，比如

```bash
objcopy -I binary test.txt -O elf64-x86-64 -B i386:x86-64 test.o
```

再使用 `nm test.o` 查看里面的符号便可以得到

```bash
000000000000000d D _binary_test_txt_end
000000000000000d A _binary_test_txt_size
0000000000000000 D _binary_test_txt_start
```

> 注意这里生成的符号名和输入的文件的路径有关，会将输入路径中的所有 `/` 和 `.` 替换成 `_`，推荐使用相对路径来获取可控的符号名。

只需在 C++ 里面声明 `_binary_test_txt_start` 上面这些符号，同时最终把 `test.o` 文件和源文件链接在一起即可。

```cpp
/// main.cpp
#include <iostream>
#include <string_view>

extern "C" {
    extern const char _binary_test_txt_start[];
    extern const char _binary_test_txt_end[];
}

int main() {
    std::cout << std::string_view(_binary_test_txt_start,
                                  _binary_test_txt_end - _binary_test_txt_start)
              << std::endl;
    return 0;
}
```

使用如下命令编译运行，就会输出 `test.txt` 里面的内容了

```bash
$ g++ -std=c++17 main.cpp test.o -o main
$ ./main
```

## Function Signature

从上面讨论中可以看出，无论是导出 kernel 函数的头文件，还是给 `cuLaunchKernel` 函数传递 kernel 函数，我们都需要获取到 kernel 的函数签名才行。然而在 CuTe DSL v4.3 中，这件事情做不完美。考虑下面这个简单的示例

```python
import torch
import cutlass.cute as cute

@cute.kernel
def test_kernel(tensor):
    cute.printf(tensor)

@cute.jit
def test(tensor):
    kernel = test_kernel(tensor)
    kernel.launch((1, 1, 1), (1, 1, 1))

a = torch.zeros([4, 3, 5]).to("cuda")
kernel = cute.compile(test, a)
print(kernel.__ptx__)
```

根据官网的文档，如果直接用 `torch.Tensor` 来实例化函数编译，那么会把它默认当做 dynamic layout。检查生成的 ptx 可以发现，kernel 的签名是

```c
.visible .entry kernel_cutlass_test_kernel_tensorptrf32_gmem_o_1_0(
        .param .align 8 .b8 kernel_cutlass_test_kernel_tensorptrf32_gmem_o_1_0_param_0[40]
)
```

也就是一个 40 字节的结构体，前 8 字节显然是一个 `float` 的指针。剩下 32 字节呢？通过进一步分析汇编可以发现，`shape` 用了 3 个 `u32` 来传参，然后有 4 字节的 padding。`stride` 用了两个 `u64` 进行传递，由于最后一维的 `stride` 是 1，所以被省略了。嗯 …… 这其实只是一个非常简单的情况，对于一些动静态 layout 混杂的情况目前我没发现通用的方法来自动生成可靠的签名。

除了 `Tensor` 直接做函数签名以外还有一些问题，比如在官方示例的 flash attn 算子里面，算子的函数签名是这样的：

```python
@cute.kernel
def kernel(
    self,
    mQ: cute.Tensor,
    mK: cute.Tensor,
    mV: cute.Tensor,
    mO: cute.Tensor,
    softmax_scale_log2: cutlass.Float32,
    sQ_layout: cute.ComposedLayout,
    sKV_layout: cute.ComposedLayout,
    sO_layout: cute.ComposedLayout,
    gmem_tiled_copy_QKV: cute.TiledCopy,
    gmem_tiled_copy_O: cute.TiledCopy,
    tiled_mma: cute.TiledMma,
    SharedStorage: cutlass.Constexpr,
):
```

这么多函数参数哪些是常量会被保留，哪些是变量不会保留呢？遗憾的是，后面这些参数在 Python 侧都是不透明的，无法进行判断，因为它们是从 C++ 侧通过 nanobind 绑定来的类型。如果你调试进去查看 kernel 最初的 mlir 的话，会发现确实会为后面这些类型生成参数，但是在后续的 pass 会删掉，而这些 pass 也是不透明的。所以我放弃了自动为 kernel 生成函数签名这一念头。

## Final Effect

采用的 workaround 则是，手动指定签名。比如我们可以人为的限制所有的算子签名都使用 `cutlass.Pointer` 和 `cute.Integer` 然后在 kernel 里面创建 `tensor`，效果上没有区别，只是人工降低了函数签名的复杂程度。或者直接看生成的 ptx 来把签名硬编码。基于这种假设和前面的步骤，我们最终可以实现如下的效果

```python3
cc = Compiler()

t = from_dlpack(torch.randn(M, N, device="cuda",
                dtype=torch.bfloat16), assumed_align=16)
cc.compile(naive_elementwise_add, [
          ("nv_bfloat16*", "a"), ("nv_bfloat16*", "b"), ("nv_bfloat16*", "o")], t, t, t)

t = from_dlpack(torch.randn(M, N, device="cuda",
                dtype=torch.float32), assumed_align=16)
cc.compile(naive_elementwise_add, [
          ("float*", "a"), ("float*", "b"), ("float*", "o")], t, t, t)

cc.link()
```

`compile` 就是收集对应的 kernel 生成的 cubin 以及 cubin 里面的函数名。`link` 就是把 cubin 变成 .o 文件，再生成一个 C++ 文件里面有所有的这些二进制数组的符号。它会为每个 kernel 生成一个对应的 wrapper，就是调用 `cuLaunchKernel` 执行对应的 kernel。最后调用 nvcc 把它们一起编译成动态库。

最后会生成这样一个头文件，以及一个动态库，供 C++ 程序调用。

```cpp
namespace cutedsl_aot {

struct LaunchParams {
    dim3 gridDim;
    dim3 blockDim;
    unsigned int sharedMemBytes = 0;
    cudaStream_t hStream = nullptr;
};

void naive_elementwise_add(const LaunchParams& params,
                           nv_bfloat16* a,
                           nv_bfloat16* b,
                           nv_bfloat16* o);

void naive_elementwise_add(const LaunchParams& params, float* a, float* b, float* o);
}  // namespace cutedsl_aot
```

这样的实现很不优雅，但从用户侧来说似乎只能做到这样了。据小道消息，CuTe DSL 的 AOT 已经**正在支持**了，让我们期待未来的更新！
