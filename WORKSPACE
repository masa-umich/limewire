load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

### Versioning ###
# Skylib
http_archive(
    name = "bazel_skylib",
    sha256 = "83084754647c9bbed2af53e2e2001f733345af020ba3a6ea222ac0596184b8c0",
    urls = ["https://github.com/bazelbuild/bazel-skylib/archive/main.zip"],
    strip_prefix = "bazel-skylib-main",
)
load("@bazel_skylib//lib:versions.bzl", "versions")
# Must be using exactly Bazel-5.3.0 (or just use bazelisk)
versions.check(minimum_bazel_version = "5.3.0", bazel_version = "5.3.0", maximum_bazel_version = "5.3.0")
# I thought this would make it so there would be an obvious error message if you're using the wrong Bazel version, but it doesn't seem to work for unknown reasons.

### Define Synnax Version ###
synnax_release = "v0.26.9"
synnax_prefix = "synnax-synnax-" + synnax_release
synnax_url = "https://github.com/synnaxlabs/synnax/archive/refs/tags/synnax-" + synnax_release + ".zip"

### External/Remote Dependencies ###
# Synnax
http_archive(
    name = "synnax",
    url = synnax_url,
    sha256 = "66a39d15869d7568bdc3c0d2972e23012bdf0f7f288d43d904700708e02d7055",
    strip_prefix = synnax_prefix,
)

# Synnax Freighter
http_archive(
    name = "Freighter",
    url = synnax_url,
    strip_prefix = synnax_release + "/freighter/cpp",
)

# Synnax Freighter Errors Protos
http_archive(
    name = "ferrors_protos",
    url = synnax_url,
    strip_prefix = synnax_prefix + "freighter/go",
)

# Synnax Telemetry Protos.
http_archive(
    name = "telem_protos",
    url = synnax_url,
    strip_prefix = synnax_prefix + "x/go/telem",
)

# Synnax API Protos.
http_archive(
    name = "api_protos",
    url = synnax_url,
    strip_prefix = synnax_prefix + "synnax/pkg/api/grpc",
)

### GRPC ###

http_archive(
    name = "rules_proto_grpc",
    strip_prefix = "rules_proto_grpc-4.5.0",
    sha256 = "9ba7299c5eb6ec45b6b9a0ceb9916d0ab96789ac8218269322f0124c0c0d24e2",
    urls = ["https://github.com/rules-proto-grpc/rules_proto_grpc/releases/download/4.5.0/rules_proto_grpc-4.5.0.tar.gz"],
)

load("@rules_proto_grpc//:repositories.bzl", "rules_proto_grpc_repos", "rules_proto_grpc_toolchains")
rules_proto_grpc_toolchains()
rules_proto_grpc_repos()
load("@rules_proto//proto:repositories.bzl", "rules_proto_dependencies", "rules_proto_toolchains")
rules_proto_dependencies()
rules_proto_toolchains()
load("@rules_proto_grpc//cpp:repositories.bzl", "cpp_repos")
cpp_repos()
load("@com_github_grpc_grpc//bazel:grpc_deps.bzl", "grpc_deps")
grpc_deps()
load("@com_github_grpc_grpc//bazel:grpc_extra_deps.bzl", "grpc_extra_deps")
grpc_extra_deps()