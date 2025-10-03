# Docker Actions

Docker actions provide container operations for extracting files from Docker images and building images.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "docker"
command = "extract|build|pull"
image = "image:tag"       # Required
# Command-specific fields below
```

## Commands

### extract

Extract files from a Docker container image.

**Required Fields:**
- `image`: Docker image name with optional tag
- `source`: Path inside container to extract
- `destination`: Local path to extract to (ResourceUrl)

**Optional Fields:**
- `tag`: Image tag (default: `latest`)

**Example:**
```toml
[[actions]]
name = "extract-python-libs"
type = "docker"
command = "extract"
image = "python"
tag = "3.12-slim"
source = "/usr/local/lib/python3.12/"
destination = "extracted:///python-libs/"
```

**Behavior:**
1. Creates temporary container from image
2. Copies files from container to local filesystem
3. Stores in `extracted:///` directory
4. Automatically cleans up container

### build

Build a Docker image from a Dockerfile.

**Required Fields:**
- `image`: Image name to create
- `path`: Path to Dockerfile directory (ResourceUrl)

**Optional Fields:**
- `tag`: Image tag (default: `latest`)
- `build_args`: Build arguments dictionary

**Example:**
```toml
[[actions]]
name = "build-app-image"
type = "docker"
command = "build"
image = "myapp"
tag = "1.0.0"
path = "repository:///"

[actions.build_args]
PYTHON_VERSION = "3.12"
APP_ENV = "production"
```

### pull

Pull a Docker image from registry.

**Required Fields:**
- `image`: Image name to pull

**Optional Fields:**
- `tag`: Image tag (default: `latest`)

**Example:**
```toml
[[actions]]
name = "pull-base-image"
type = "docker"
command = "pull"
image = "python"
tag = "3.12-slim"
```

## Common Use Cases

### Extract Configuration Files

```toml
[[actions]]
name = "extract-nginx-config"
type = "docker"
command = "extract"
image = "nginx"
tag = "latest"
source = "/etc/nginx/"
destination = "extracted:///nginx-config/"

[[actions]]
name = "copy-to-repo"
type = "file"
command = "copy"
source = "extracted:///nginx-config/nginx.conf"
destination = "repository:///config/nginx.conf"
```

### Extract Python Packages

```toml
[[actions]]
name = "extract-site-packages"
type = "docker"
command = "extract"
image = "myapp"
tag = "latest"
source = "/usr/local/lib/python3.12/site-packages/"
destination = "extracted:///packages/"
```

### Build Custom Image

```toml
[[actions]]
name = "create-dockerfile"
type = "template"
source_path = "workflow:///Dockerfile.j2"
destination_path = "repository:///Dockerfile"

[[actions]]
name = "build-image"
type = "docker"
command = "build"
image = "{{ imbi_project.slug }}"
tag = "{{ version }}"
path = "repository:///"
```

## Implementation Notes

- Requires Docker daemon running
- Uses `docker` CLI commands
- Temporary containers automatically cleaned up
- Extracted files preserve permissions
- Build context is the specified path directory
