#!/bin/bash -e
#
# Common functions for the scripts
#

die() {
    echo "$@"
    exit 1
}


build_docs() {
    local docs_dir="${1?}"
    local res=0
    rm -rf "$docs_dir"
    rm -rf tests/docs_venv
    [[ -d .cache ]] || mkdir .cache
    chown -R $USER .cache
    virtualenv -q tests/docs_venv || return 1
    source tests/docs_venv/bin/activate
    pip --quiet install --upgrade pip || return 1
    pip --quiet install --requirement docs/requires.txt || return 1
    make docs || res=$?
    deactivate
    mv docs/build "$docs_dir"
    return $res
}


generate_html_report() {
    cat  >exported-artifacts/index.html <<EOR
    <html>
    <body>
        <ul>
            <li>
                <a href="docs/html/index.html">Docs page</a>
            </li>
        </ul>
    </body>
    </html>
EOR
    echo "~ Report at file://$PWD/exported-artifacts/index.html  ~"
}

