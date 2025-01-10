---
title: 'Super Useful C++ Online Compiler (VSCode Edition)'
date: 2024-04-24 21:35:41
updated: 2024-05-04 16:48:53
---

[Compiler Explorer](https://godbolt.org/) is a highly popular online C++ compiler that can be used to test different compilation and execution environments or to share code. As a C++ enthusiast, I interact with it almost daily, far more frequently than I initially imagined. Additionally, I am a heavy VSCode user, handling almost all tasks within VSCode. Considering the frequent need to write code locally and then copy it to Compiler Explorer, it often feels cumbersome. Sometimes, I directly modify the code in its web editor, but without code completion, it's equally uncomfortable. Therefore, in collaboration with [@iiirhe](https://www.zhihu.com/people/32ffceca937677f7950b64e5186bb998), we developed this plugin [Compiler Explorer for VSCode](https://marketplace.visualstudio.com/items?itemName=ykiko.vscode-compiler-explorer), which integrates Compiler Explorer into VSCode using the [API](https://github.com/compiler-explorer/compiler-explorer/blob/main/docs/API.md) provided by Compiler Explorer, allowing users to directly utilize Compiler Explorer's functionalities within VSCode.

Now you can search for this plugin in the VSCode marketplace.

![](https://picx.zhimg.com/v2-ebff5a9177bf7dbab863e321db8f05f3_r.jpg)

### Demonstration

![](https://pic2.zhimg.com/v2-4d92bdc32a6479e20a8b54b776b4618f_r.jpg)

### Single File Support

![](https://picx.zhimg.com/v2-f8b679e187c025f49cac898d60a66653_r.jpg)

Let's introduce from top to bottom.

![](https://pic1.zhimg.com/v2-702bddfa45a016fdad36c70cc95d88fa_r.jpg)

The functions of these three buttons are as follows:

- `Compile All`: Compile all compiler instances.
- `Add New`: Add a new compiler instance.
- `Share Link`: Generate a link based on the current compiler instance and copy it to the clipboard.

![](https://pic1.zhimg.com/v2-abca330d863e476211dc21f969616da0_b.jpg)

The functions of these four buttons are as follows:

- `Add CMake`: Add a CMake compiler instance (details will be discussed later).
- `Clear All`: Close all displayed `webview` panels.
- `Load Link`: Load compiler instance information based on the input link.
- `Remove All`: Delete all compiler instances.

![](https://pic1.zhimg.com/v2-4563375d43c5084354585cec8dc1c692_r.jpg)

The functions of these three buttons are as follows:

- `Run`: Compile this compiler instance.
- `Clone`: Clone this compiler instance.
- `Remove`: Delete this compiler instance.

Below are the parameters for setting up the compiler instance:

- `Compiler`: Click the button on the right to select the compiler version.
- `Input`: Select the source code file, default is `active`, i.e., the currently active editor.
- `Output`: The file to output the compilation results, default uses `webview`.
- `Options`: Compilation options, click the button on the right to open the input box.
- `Execute Arguments`: Arguments passed to the executable.
- `Stdin`: Buffer for standard input.
- `Filters`: Some options.

### Multi-File Support

Using the `Add CMake` button, you can add a CMake compiler instance, which can be used to compile multiple files.

![](https://picx.zhimg.com/v2-e22f7b14430ce8bfb84ad9be28f2e55f_r.jpg)

<br>

Most options are the same as the single-file compiler instance, with two additional ones:

- `CMake Arguments`: Arguments passed to CMake.
- `Source`: The path to the folder containing CMakelists.txt.

Note, since multi-file compilation requires uploading all used files to the server, we default to reading all files in the specified directory (regardless of the file extension), **so please do not specify folders with too many files at this time**. We may add options to allow users to filter out some files in the future, but not currently.

### Some User Settings

`compiler-explorer.default.options`: Default parameters when creating a compiler with the `+` sign.

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

`compiler-explorer.default.color`: Used to specify the color for highlighting assembly code.

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

`compiler-explorer.default.url`: The default link loaded when opening the plugin, default is empty.

```json
"compiler-explorer.default.url": {
  "default": ""
}
```

### Feedback

This plugin is still in its early stages. If you encounter any issues during use or have any suggestions, please feel free to leave a message on [GitHub](https://github.com/16bit-ykiko/vscode-compiler-explorer) for discussion. Or join the QQ group: `662499937`.

https://qm.qq.com/q/DiO6rvnbHi (QR code automatically recognized)

Additionally, the Output window may provide some useful information, so please pay attention to it.

![](https://picx.zhimg.com/v2-6164a9cf19c1c1e4fc1d44809c726441_r.jpg)