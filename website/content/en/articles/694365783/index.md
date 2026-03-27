---
title: Super easy-to-use C++ Online Compiler (VSCode Version)
date: "2024-04-24 13:35:41"
updated: "2024-05-04 08:48:53"
zhihu_article_id: "694365783"
zhihu_url: https://zhuanlan.zhihu.com/p/694365783
---

> This article was translated by AI using Gemini 2.5 Pro from the original Chinese version. Minor inaccuracies may remain.

[Compiler Explorer](https://godbolt.org/) is a very popular online C++ compiler, which can be used to test different compilation and execution environments, or to share code. As a C++ enthusiast, I interact with it almost every day, and its frequency of use far exceeds my imagination. At the same time, I am also a heavy VSCode user, completing almost everything within VSCode. Considering that I often write code locally and then copy it to Compiler Explorer, it always felt uncomfortable. Sometimes I would directly modify it on its web editor, but without code completion, that was also uncomfortable. Therefore, I collaborated with [@iiirhe](https://www.zhihu.com/people/32ffceca937677f7950b64e5186bb998) to write this extension [Compiler Explorer for VSCode](https://marketplace.visualstudio.com/items?itemName=ykiko.vscode-compiler-explorer), which integrates Compiler Explorer into VSCode based on the [API](https://github.com/compiler-explorer/compiler-explorer/blob/main/docs/API.md) provided by Compiler Explorer, allowing users to directly use Compiler Explorer's features within VSCode.

You can now search for this extension in the VSCode Marketplace.

![](https://picx.zhimg.com/v2-ebff5a9177bf7dbab863e321db8f05f3_r.jpg)

### Demo

![](https://pic2.zhimg.com/v2-4d92bdc32a6479e20a8b54b776b4618f_r.jpg)

### Single File Support

![](https://picx.zhimg.com/v2-f8b679e187c025f49cac898d60a66653_r.jpg)

Let's introduce them from top to bottom.

![](https://pic1.zhimg.com/v2-702bddfa45a016fdad36c70cc95d88fa_r.jpg)

The functions of these three buttons are, in order:

- `Compile All`: Compiles all compiler instances
- `Add New`: Adds a new compiler instance
- `Share Link`: Generates a link based on the current compiler instance and copies it to the clipboard

![](https://pic1.zhimg.com/v2-abca330d863e476211dc21f969616da0_b.jpg)

The functions of these four buttons are, in order:

- `Add CMake`: Adds a CMake compiler instance (more details later)
- `Clear All`: Closes all `webview` panels used for display
- `Load Link`: Loads compiler instance information based on the input link
- `Remove All`: Removes all compiler instances

![](https://pic1.zhimg.com/v2-4563375d454585cec8dc1c692_r.jpg)

The functions of these three buttons are, in order:

- `Run`: Compiles this compiler instance
- `Clone`: Clones this compiler instance
- `Remove`: Removes this compiler instance

The following parameters are used to configure compiler instances:

- `Compiler`: Click the button on the right to select the compiler version
- `Input`: Select the source code file, default is `active` (the currently active editor)
- `Output`: Output file for compilation results, `webview` by default
- `Options`: Compilation options, click the button on the right to open the input box
- `Execute Arguments`: Arguments passed to the executable
- `Stdin`: Buffer for standard input
- `Filters`: Some options

### Multi-file Support

You can add a CMake compiler instance using the `Add CMake` button, which can be used to compile multiple files.

![](https://picx.zhimg.com/v2-e22f7b14430ce8bfb84ad9be28f2e55f_r.jpg)

<br>

Most options are the same as for single-file compiler instances, with two additional ones:

- `CMake Arguments`: Arguments passed to CMake
- `Source`: Path to the folder containing CMakeLists.txt

Note that since multi-file compilation requires uploading all used files to the server, we will by default read all files (regardless of extension) in the directory you specify. **Therefore, please do not specify folders with too many files for now.** Options to allow users to filter out some files might be added later, but are not available yet.

### User Settings

`compiler-explorer.default.options`: Default parameters when creating a compiler using the `+` sign

```json
"compiler-explorer.default.options": {
  "type": "object",
  "description": "The default compiler configuration",
  "default": {
    "compiler": "x86-64 gcc 13.2",
    "language": "c++",
    "options": "-std=c++17",
    "exec": "",
    "stdin": "",
    "cmakeArgs": "",
    "src": "workspace",
    "filters": {
      "binaryObject": false,
      "binary": false,
      "execute": false,
      "intel": true,
      "demangle": true,
      "labels": true,
      "libraryCode": true,
      "directives": true,
      "commentOnly": true,
      "trim": false,
      "debugCalls": false
    }
  }
}
```

`compiler-explorer.default.color`: Used to specify the color for highlighting assembly code

```json
"compiler-explorer.default.color":{
    "symbol": "#61AFEF",
    "string": "#98C379",
    "number": "#D19A66",
    "register": "#E5C07B",
    "instruction": "#C678DD",
    "comment": "#7F848E",
    "operator": "#ABB2BF"
}
```

`compiler-explorer.default.url`: The default link loaded when opening the extension, empty by default

```json
"compiler-explorer.default.url": {
  "default": ""
}
```

### Feedback

This extension is still in its early stages. If you encounter any problems during use, or have any suggestions, please feel free to leave a message and discuss it on [GitHub](https://github.com/16bit-ykiko/vscode-compiler-explorer). Alternatively, join the QQ group: `662499937`.

https://qm.qq.com/q/DiO6rvnbHi (QR code auto-recognition)

Additionally, the Output window may provide some useful information, which you can check.

![](https://picx.zhimg.com/v2-6164a9cf19c1c1e4fc1d44809c726441_r.jpg)
