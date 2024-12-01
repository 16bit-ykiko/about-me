all: list['Article'] = []


class Article:
    def __init__(self, url: str, tags: list[str], series: tuple[str, int] | None = None):
        self.url = url
        self.tags = tags
        self.series = series
        all.append(self)


Article("https://zhuanlan.zhihu.com/p/645810896", ["C++", "STL", "Template"])

# STMP Series
Article("https://zhuanlan.zhihu.com/p/646752343",
        ["C++", "STL", "Template", "STMP"], series=("STMP", 1))
Article("https://zhuanlan.zhihu.com/p/646812253",
        ["C++", "STL", "Template", "STMP"], series=("STMP", 2))

Article("https://zhuanlan.zhihu.com/p/655902377",
        ["C++", "Template, Overview"])
Article("https://zhuanlan.zhihu.com/p/659510753", ["C++", "Language Feature"])

# Reflection Series
Article("https://zhuanlan.zhihu.com/p/661692275",
        tags=["C++", "C++26", "Reflection"], series=("Reflection", 6))
Article("https://zhuanlan.zhihu.com/p/669358870",
        tags=["C++", "Template", "Reflection"], series=("Reflection", 1))
Article("https://zhuanlan.zhihu.com/p/669359855",
        tags=["C++", "Reflection", "Code Generation"], series=("Reflection", 4))
Article("https://zhuanlan.zhihu.com/p/669360731",
        tags=["C++", "Reflection", "Code Generation", "Parser"], series=("Reflection", 5))
Article("https://zhuanlan.zhihu.com/p/670190357",
        tags=["C++", "Reflection", "Metainfo"], series=("Reflection", 2))
Article("https://zhuanlan.zhihu.com/p/670191053",
        tags=["C++", "Reflection", "Type Ensure"], series=("Reflection", 3))

Article("https://zhuanlan.zhihu.com/p/674157958", ["C++", "Template"])
Article("https://zhuanlan.zhihu.com/p/679782886",
        ["C++", "Relocatable", "STL"])
Article("https://zhuanlan.zhihu.com/p/680412313", ["C++", "Template"])

# Constexpr Series
Article("https://zhuanlan.zhihu.com/p/682031684",
        ["C++", "Constexpr"], series=("Constexpr", 1))
Article("https://zhuanlan.zhihu.com/p/683463723",
        ["C++", "Constexpr"], series=("Constexpr", 2))

Article("https://zhuanlan.zhihu.com/p/686296374",
        ["C++", "Template", "Binary inflation"])
Article("https://zhuanlan.zhihu.com/p/692886292", ["C++", "ABI", "OS"])
Article("https://zhuanlan.zhihu.com/p/694365783", ["C++", "Tool"])
Article("https://zhuanlan.zhihu.com/p/696878184", ["C++", "STL"])
Article("https://zhuanlan.zhihu.com/p/702197261", ["C++", "STL", "Python"])
Article("https://zhuanlan.zhihu.com/p/706509748", ["C++"])
