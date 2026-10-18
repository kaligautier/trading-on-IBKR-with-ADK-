"""Validate a complete GitHub PR file listing against the triggering head."""


def changed_files(report: dict, pages: list, expected_head: str) -> list[dict]:
    if not expected_head or report.get("head", {}).get("sha") != expected_head:
        raise ValueError("PR head changed; the latest run must validate its changes.")
    count = report.get("changed_files")
    if type(count) is not int or count < 0:
        raise ValueError("GitHub did not return a valid changed-file count.")
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("GitHub did not return paginated PR files.")
    files = [entry for page in pages for entry in page]
    if len(files) != count:
        raise ValueError("Incomplete PR file list; changes cannot be verified.")
    seen = set()
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
            raise ValueError("GitHub returned an invalid PR file.")
        name = entry["filename"]
        if not name or name in seen:
            raise ValueError("GitHub returned an empty or duplicate PR filename.")
        seen.add(name)
    return files
