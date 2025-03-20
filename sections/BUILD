build_types = load("//infra/build_types.py")
check_types = load("//infra/check_types.py")
rules = load("//infra/rules.py")

rules.declare_library_usage(
    name=f"sections_common_js",
    base="src",
    dep=":common",
)

build_types.declare_react_app(
    name="sections_app",
    srcs=depset(
        find("**/*.*", unsafe_ignore_extension=True),
        ".flowconfig",
        ".eslintrc.js",
        ".prettierrc.json",
    ),
    deps=[":common"],
    include=[":sections_common_js"],
    checks=[
        check_types.yarn(prettier=True, eslint=True, flow=True),
    ],
)
