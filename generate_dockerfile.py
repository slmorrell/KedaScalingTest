#!/usr/bin/env python3
"""
Azure Functions Dockerfile Generator
=====================================
Generates a standard multi-stage Dockerfile (and optionally a docker-compose.yaml)
for .NET isolated Azure Functions projects.

Usage
-----
Generate only a Dockerfile:
    python generate_dockerfile.py --project-name MyService

Generate a Dockerfile + docker-compose.yaml:
    python generate_dockerfile.py --project-name MyService --compose

Target the appservice image variant (enables SSH / remote debugging):
    python generate_dockerfile.py --project-name MyService --appservice

Write files to a custom output directory:
    python generate_dockerfile.py --project-name MyApi --output ./infra

All options:
    --project-name      Required. The project name used for the Docker image tag
                        (e.g. "MyService" → image "myservice:local").
    --dotnet-version    .NET SDK / runtime version.  Default: 8.0
    --functions-version Azure Functions host major version.  Default: 4
    --appservice        Switch the runtime base image to the *-appservice variant,
                        which enables SSH and remote debugging on App Service.
    --port              Host port mapped to the container's port 80 in
                        docker-compose.  Default: 7071
    --compose           Also generate a docker-compose.yaml next to the Dockerfile.
    --output            Directory where files are written.  Default: . (current dir)
"""

import argparse
import os
import sys


# ---------------------------------------------------------------------------
# Template builders
# ---------------------------------------------------------------------------

def build_dockerfile(dotnet_version: str, functions_version: str, appservice: bool) -> str:
    appservice_suffix = "-appservice" if appservice else ""
    runtime_image = (
        f"mcr.microsoft.com/azure-functions/dotnet-isolated:"
        f"{functions_version}-dotnet-isolated{dotnet_version}{appservice_suffix}"
    )
    sdk_image = f"mcr.microsoft.com/dotnet/sdk:{dotnet_version}"

    appservice_comment = (
        "# SSH & remote debugging are enabled because the appservice image variant is used.\n"
        if appservice
        else (
            "# To enable ssh & remote debugging on app service change the base image to the one below\n"
            f"# FROM mcr.microsoft.com/azure-functions/dotnet-isolated:"
            f"{functions_version}-dotnet-isolated{dotnet_version}-appservice\n"
        )
    )

    return (
        f"FROM {sdk_image} AS installer-env\n"
        "\n"
        "COPY . /src/dotnet-function-app\n"
        "RUN cd /src/dotnet-function-app && \\\n"
        "    mkdir -p /home/site/wwwroot && \\\n"
        "    dotnet publish *.csproj --output /home/site/wwwroot\n"
        "\n"
        f"{appservice_comment}"
        f"FROM {runtime_image}\n"
        "ENV AzureWebJobsScriptRoot=/home/site/wwwroot \\\n"
        "    AzureFunctionsJobHost__Logging__Console__IsEnabled=true\n"
        "EXPOSE 80\n"
        'COPY --from=installer-env ["/home/site/wwwroot", "/home/site/wwwroot"]\n'
    )


def build_compose(project_name: str, port: int) -> str:
    image_name = f"{project_name.lower()}:local"
    azurite_conn = (
        "DefaultEndpointsProtocol=http;"
        "AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        "BlobEndpoint=http://azurite:10000/devstoreaccount1;"
        "QueueEndpoint=http://azurite:10001/devstoreaccount1;"
        "TableEndpoint=http://azurite:10002/devstoreaccount1"
    )

    return (
        "services:\n"
        "  azurite:\n"
        "    image: mcr.microsoft.com/azure-storage/azurite\n"
        "    ports:\n"
        '      - "10000:10000"\n'
        '      - "10001:10001"\n'
        '      - "10002:10002"\n'
        "\n"
        "  functions:\n"
        "    build:\n"
        "      context: .\n"
        "      dockerfile: Dockerfile\n"
        f"    image: {image_name}\n"
        "    ports:\n"
        f'      - "{port}:80"\n'
        "    environment:\n"
        "      FUNCTIONS_WORKER_RUNTIME: dotnet-isolated\n"
        f'      AzureWebJobsStorage: "{azurite_conn}"\n'
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a standard Azure Functions Dockerfile (and optional docker-compose.yaml).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="Project name used for the Docker image tag (e.g. MyService).",
    )
    parser.add_argument(
        "--dotnet-version",
        default="8.0",
        help=".NET SDK/runtime version (default: 8.0).",
    )
    parser.add_argument(
        "--functions-version",
        default="4",
        help="Azure Functions host major version (default: 4).",
    )
    parser.add_argument(
        "--appservice",
        action="store_true",
        help="Use the *-appservice image variant (enables SSH / remote debugging).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7071,
        help="Host port mapped to container port 80 in docker-compose (default: 7071).",
    )
    parser.add_argument(
        "--compose",
        action="store_true",
        help="Also generate a docker-compose.yaml alongside the Dockerfile.",
    )
    parser.add_argument(
        "--output",
        default=".",
        help="Directory where generated files are written (default: current directory).",
    )
    return parser.parse_args()


def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def main() -> None:
    args = parse_args()

    output_dir = os.path.abspath(args.output)
    if not os.path.isdir(output_dir):
        print(f"Error: output directory '{output_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    dockerfile_path = os.path.join(output_dir, "Dockerfile")
    dockerfile_content = build_dockerfile(
        dotnet_version=args.dotnet_version,
        functions_version=args.functions_version,
        appservice=args.appservice,
    )
    write_file(dockerfile_path, dockerfile_content)

    files_written = [dockerfile_path]

    if args.compose:
        compose_path = os.path.join(output_dir, "docker-compose.yaml")
        compose_content = build_compose(
            project_name=args.project_name,
            port=args.port,
        )
        write_file(compose_path, compose_content)
        files_written.append(compose_path)

    # Summary
    appservice_label = " (appservice variant)" if args.appservice else ""
    print("✅ Files generated successfully!")
    print()
    print("Settings:")
    print(f"  Project name      : {args.project_name}")
    print(f"  .NET version      : {args.dotnet_version}")
    print(f"  Functions version : {args.functions_version}{appservice_label}")
    if args.compose:
        print(f"  Host port         : {args.port}")
    print()
    print("Files written:")
    for path in files_written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
