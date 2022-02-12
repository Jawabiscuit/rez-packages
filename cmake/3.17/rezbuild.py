import fnmatch
import os
import platform
import shutil
import sys
import tarfile
import zipfile


project_name = os.environ["REZ_BUILD_PROJECT_NAME"]
project_version = os.environ["REZ_BUILD_PROJECT_VERSION"]

archive_filename = "{project_name}-{project_version}-win64-x64.zip".format(
    project_name=project_name, project_version=project_version
)
url_prefix = "https://github.com/Kitware/CMake/releases/download/v{project_version}".format(
    project_version=project_version
)


def Python3():
    return sys.version_info.major == 3


def download(url, file_name, dst_dir="."):
    """Download file into current dir or `dst_dir`
    Download will be skipped if file exists
    """
    if Python3():
        import urllib.request as urllib
    else:
        import urllib2 as urllib

    file_path = os.path.abspath(os.path.join(dst_dir, file_name))

    if os.path.isfile(file_path):
        print("File exists, skip download: {}".format(file_path))
        return file_path

    print("Downloading from {}\n\t-> {}".format(url, file_path))
    urlhandle = urllib.urlopen(url)
    filehandle = open(file_path, "wb")

    # Get content length (file size)
    meta = urlhandle.info()
    try:
        if hasattr(meta, "getheader"):
            file_size = int(meta.getheaders("Content-Length")[0])
        else:
            file_size = int(meta.get("Content-Length")[0])
        print("Downloading: {} Bytes: {}".format(file_path, file_size))
    except (IndexError, TypeError):
        file_size = None
        print("Downloading: {} Bytes: {}".format(file_path, "Unknown"))

    # Download with progress bar
    file_size_dl = 0
    block_size = 8192
    while True:
        buffer = urlhandle.read(block_size)
        if not buffer:
            break

        file_size_dl += len(buffer)
        filehandle.write(buffer)
        if file_size is not None:
            status = "\r{:10d}  [{:3.2f}%]".format(file_size_dl, file_size_dl * 100. / file_size)
            if Python3():
                exec("print(status, end='\\r')", {"status": status})
            else:
                exec("print status, ", {"status": status})

    filehandle.close()
    return file_path


def open_archive(file_path, skip_extract=None, extract=False):
    """Extract archive file (zip/tar) in current working dir
    
    Archive will first temporally extract into `./extract_dir`, and
    move extracted content into `root_dir`.

    If `extract` is `False`, return the archive root dir without
    extracting.
    """
    # Open the archive and retrieve the name of the top-most directory.
    # This assumes the archive contains a single directory with all
    # of the contents beneath it.
    if tarfile.is_tarfile(file_path):
        archive = tarfile.open(file_path)
        members = archive.getmembers()

        if skip_extract is not None:
            members = [m for m in members
                        if not any((fnmatch.fnmatch(m.name, p)
                                    for p in skip_extract))]
        if not Python3():
            for m in members:
                m.name = m.name.decode("utf-8")
        root_dir = [m.name for m in members][0].split('/')[0]
        if not extract:
            return root_dir

    elif zipfile.is_zipfile(file_path):
        archive = zipfile.ZipFile(file_path)
        members = archive.namelist()

        if skip_extract is not None:
            members = (m for m in members
                        if not any((fnmatch.fnmatch(m, p)
                                    for p in skip_extract)))
            members = list(members)
        root_dir = members[0].split('/')[0]
        if not extract:
            return root_dir
    else:
        raise RuntimeError("unrecognized archive file type")

    with archive:
        tmp_extracted_path = os.path.abspath("extract_dir")
        extracted_path = os.path.abspath(root_dir)

        if os.path.isdir(extracted_path):
            print("Cleaning previous extract: {}".format(extracted_path))
            shutil.rmtree(extracted_path, ignore_errors=True)

        print("Extracting archive to {}".format(extracted_path))
        if os.path.isdir(tmp_extracted_path):
            shutil.rmtree(tmp_extracted_path, ignore_errors=True)

        archive.extractall(tmp_extracted_path, members=members)

        shutil.move(os.path.join(tmp_extracted_path, root_dir), extracted_path)
        shutil.rmtree(tmp_extracted_path, ignore_errors=True)

        return extracted_path


def build(source_path, build_path, install_path, targets=None, build_args=None):
    """Download and extract source, install if `install` in `targets`
    
    Skip extraction if `no_build` in `build_args`.
    """
    targets = targets or []
    install = 'install' in targets
    extract = "extract" in build_args

    def _build():
        """Download and extract the source"""
        url = "{}/{}".format(url_prefix, archive_filename)
        # Will skip if archive already exists
        archive = download(url, archive_filename)
        try:
            src_root = open_archive(archive, extract=extract)
        except Exception as e:
            raise RuntimeError(
                "Failed to extract archive {filename}: {err}".format(filename=archive, err=e)
            )
        return src_root

    def _install():
        """Copy source content to install location"""
        paths = []
        for name in os.listdir(src_root):
            src = os.path.join(src_root, name)
            dest = os.path.join(install_path, name)
            paths.append((src, dest))
        if os.path.isdir(install_path):
            shutil.rmtree(install_path)
        _copy_trees(paths)

    def _copy_trees(paths):
        """Copy a list of directories pairs"""
        for src, dest in paths:
            # if os.path.exists(dest):
            #     shutil.rmtree(dest)
            if os.path.exists(src):
                print("Installing: {}\n\t-> {}".format(src, dest))
                shutil.copytree(src, dest)
    
    src_root = _build()
    if install:
        _install()


if __name__ == "__main__":
    """
    # Build
    >>> rez build
    # Install without extraction process
    >>> rez build -i -- --no-extract
    # Probably much less common, but still valid
    >>> rez build -- --no-extract
    # Probably never, not valid
    >>> rez build -ic -- --no-extract
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    # Runs the extraction process by default, unless this flag is present
    parser.add_argument("--no-extract", action="store_true")

    if "install" in sys.argv:
        sys.argv.remove("install")
        sys.argv.append("--install")
    if "no-extract" in sys.argv:
        sys.argv.remove("no-extract")
        sys.argv.append("--no-extract")

    args = parser.parse_args(sys.argv[1:])
    targets = ["install"] if args.install else []

    build_args = []
    if not args.no_extract:
        build_args.append("extract")

    build(
        source_path=os.environ["REZ_BUILD_SOURCE_PATH"],
        build_path=os.environ["REZ_BUILD_PATH"],
        install_path=os.environ["REZ_BUILD_INSTALL_PATH"],
        targets=targets,
        build_args=build_args
    )