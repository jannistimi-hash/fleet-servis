name: Build Android APK
on: [push, workflow_dispatch]
jobs:
  build:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-python-version: '3.10'
      - name: Install Buildozer and Dependencies
        run: |
          pip install buildozer cython
          sudo apt-get install -y libsqlite3-dev openjdk-17-jdk-headless
          buildozer init
          sed -i 's/requirements = python3, kivy/requirements = python3, kivy, sqlite3/g' buildozer.spec
      - name: Build with Buildozer
        run: buildozer -v android debug
      - name: Upload APK
        uses: actions/upload-artifact@v3
        with:
          name: fleet-app-apk
          path: bin/*.apk
