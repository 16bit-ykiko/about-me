---
title: Support AOT for CuTe DSL
date: "2025-11-11 13:38:08"
updated: "2026-03-28 04:18:38"
zhihu_article_id: "1971691994037334904"
zhihu_url: https://zhuanlan.zhihu.com/p/1971691994037334904
---

>

## Why do we need AOT for CuTe DSL?

CUTLASS C++ is a library for writing high-performance CUDA operators, known for its complexity and difficulty. To reduce the learning curve, NVIDIA introduced the Python-based [CuTe DSL](https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/overview.html). Using Python instead of C++ templates for metaprogramming offers many benefits. First, users no longer have to struggle with the obscure template errors of C++, which is a major headache for C++ beginners; now they can focus on the code logic. Additionally, `nvcc` compilation is slow, and most of that time is spent in the compiler frontend, parsing C++ code. Especially for template-heavy libraries like CUTLASS, most of the time is spent processing template instantiations. Using CuTe DSL can bypass this issue. Compared to C++ code using CUTLASS, its compilation speed can be tens or even hundreds of times faster. Furthermore, operators and unit tests can now be written together in Python, which is much more convenient.

Using Python for prototyping is excellent, but when deploying inference services, we want dependencies to be as simple as possible. Having a large number of Python dependencies that could crash due to version issues is undesirable. It would be great if operators written with CuTe DSL could be compiled into a library for C++ code to call. This is precisely why we want to support AOT for CuTe DSL.

## Export Binary

CuTe DSL in [v4.3](https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/cute_dsl_general/debugging.html) added options to export the ptx and cubin for compiled kernels. Set the following environment variables:

```bash
export CUTE_DSL_KEEP_PTX=1
export CUTE_DSL_KEEP_CUBIN=1
export CUTE_DSL_DUMP_DIR=/tmp
```

You can directly access the `__ptx__` or `__cubin__` attributes of the kernel to get the corresponding values:

```bash
compiled_foo = cute.compile(foo, ...)
print(f"PTX: {compiled_foo.__ptx__}")
with open("foo.cubin", "wb") as f:
    f.write(compiled_foo.__cubin__)
```

So now we have the cubin file for the operator. The remaining questions are:

1. How to load cubin-formatted operators in C++ code.
2. How to embed the cubin file into C++ code and compile it into a library.
3. How to generate a `.h` header file for downstream users to call.

## CUDA Driver API

For question 1, we can use the [CUDA Driver API](https://docs.nvidia.com/cuda/cuda-driver-api/index.html).

```bash
CUresult CUDAAPI cuModuleLoadData(CUmodule *module, const void *image);
CUresult CUDAAPI cuModuleGetFunction(CUfunction *hfunc, CUmodule hmod, const char *name);
```

Load the cubin file with `cuModuleLoadData` and get the kernel function with `cuModuleGetFunction`.

```bash
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

Then launch the kernel with `cuLaunchKernel`. It's worth noting that kernel parameters are passed via `void**`, i.e., an array of `void*`, which means we need to know the kernel's function signature to launch it.

## Embed Binary

For question 2, we need a way to embed binary files into C++ files, and then directly reference the kernel in the C++ file. The discussion on how to embed binary files in C++ code deserves a separate article, so I won't elaborate too much here. I'll just mention the method I chose. Use `objcopy` to convert the binary file into an ELF-formatted file, and at the same time, it will insert several symbols for referencing the binary data, for example:

```bash
objcopy -I binary test.txt -O elf64-x86-64 -B i386:x86-64 test.o
```

Then use `nm test.o` to view the symbols within:

```bash
000000000000000d D _binary_test_txt_end
000000000000000d A _binary_test_txt_size
0000000000000000 D _binary_test_txt_start
```

>

You just need to declare these symbols like `_binary_test_txt_start` in C++, and finally link the `test.o` file with the source file.

```bash
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

Compile and run with the following commands, and it will output the content of `test.txt`:

```bash
$ g++ -std=c++17 main.cpp test.o -o main
$ ./main
```

## Function Signature

From the discussion above, it's clear that whether exporting header files for kernel functions or passing kernel functions to `cuLaunchKernel`, we need to obtain the kernel's function signature. However, in CuTe DSL v4.3, this cannot be done perfectly. Consider this simple example:

```bash
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

According to the official documentation, if `torch.Tensor` is used directly to instantiate the function for compilation, it will be treated as a dynamic layout by default. Inspecting the generated ptx reveals that the kernel's signature is:

```bash
.visible .entry kernel_cutlass_test_kernel_tensorptrf32_gmem_o_1_0(
        .param .align 8 .b8 kernel_cutlass_test_kernel_tensorptrf32_gmem_o_1_0_param_0[40]
)
```

This is a 40-byte struct, where the first 8 bytes are clearly a `float` pointer. What about the remaining 32 bytes? Further analysis of the assembly shows that `shape` uses 3 `u32`s for parameters, followed by 4 bytes of padding. `stride` uses two `u64`s for passing, and since the stride of the last dimension is 1, it is omitted. Well... this is actually a very simple case. For situations where dynamic and static layouts are mixed, I haven't found a general method to automatically generate reliable signatures.

Besides `Tensor` directly serving as a function signature, there are other issues. For example, in the official flash attention operator example, the operator's function signature is like this:

```bash
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

Among these many function parameters, which ones are constants that will be preserved, and which ones are variables that will not? Unfortunately, these latter parameters are opaque on the Python side and cannot be determined because they are types bound from the C++ side via nanobind. If you debug and look at the kernel's initial MLIR, you will find that parameters are indeed generated for these types, but they are deleted in subsequent passes, and these passes are also opaque. So I gave up on the idea of automatically generating function signatures for kernels.

## Final Effect

The workaround adopted is to manually specify the signature. For example, we can artificially restrict all operator signatures to use `cutlass.Pointer` and `cute.Integer` and then create the `tensor` inside the kernel. The effect is the same, it just manually reduces the complexity of the function signature. Or, one could directly hardcode the signature by looking at the generated ptx. Based on this assumption and the previous steps, we can ultimately achieve the following effect:

```bash
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

`compile` collects the cubin generated for the corresponding kernel and the function names within the cubin. `link` converts the cubin into `.o` files and then generates a C++ file containing symbols for all these binary arrays. It will generate a corresponding wrapper for each kernel, which calls `cuLaunchKernel` to execute the respective kernel. Finally, `nvcc` compiles them together into a dynamic library.

This will ultimately generate a header file and a dynamic library, for C++ programs to call.

```bash
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

This implementation is not very elegant, but from the user's perspective, it seems to be the best we can do. According to unofficial sources, AOT for CuTe DSL is **currently being supported**. Let's look forward to future updates!
