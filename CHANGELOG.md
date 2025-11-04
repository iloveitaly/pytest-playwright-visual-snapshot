# Changelog

## [0.2.4](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/compare/v0.2.3...v0.2.4) (2025-11-04)


### Documentation

* delete unneeded copier.yml file ([4d6f8df](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/4d6f8df9b3dd7171ba00bc2ec90d61f7f2f45e13))

## [0.2.3](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/compare/v0.2.2...v0.2.3) (2025-07-02)


### Bug Fixes

* prevent FileExistsError for creating snapshot failures directory when tests run in parallel ([63b9bc7](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/63b9bc7a96d1bd1afdca45e7f1b108f5676728c2))

## [0.2.2](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/compare/v0.2.1...v0.2.2) (2025-06-25)


### Bug Fixes

* only cleanup snapshot failures at the beginning of the test suite ([c1d9427](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/c1d94277c7c627e9f342adcbc36fcab5ecc83a45))


### Documentation

* add note on CI Chrome differences and screenshot usage ([6ee2015](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/6ee2015a679c0adc9ca82010a9a725d4563bf810))

## [0.2.1](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/compare/v0.2.0...v0.2.1) (2025-04-14)


### Bug Fixes

* remove failures at the beginning of the pytest run ([9361cda](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/9361cda1cbf8b7faa7842eaa9b5ef8dc192e8527))


### Documentation

* add GitHub Actions script for snapshot management ([fa33c51](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/fa33c51b9d699fa4608763b7b1dc90a22e382cb7))
* update todo ([8ca78cb](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/8ca78cbfb88ea43cd6256fb32f75d1b59e3b0c60))

## [0.2.0](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/compare/v0.1.0...v0.2.0) (2025-03-25)


### Features

* add CSS masking for visual snapshots in pytest plugin ([6b62602](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/6b62602750052980fc0d92db1cdbdc7154c05c2c))
* batch snapshot failure messages in assert_snapshot ([95584b4](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/95584b4ff6be8bd50cb24781d3e61357ca3cec19))


### Bug Fixes

* use PNG format for snapshots and update messages ([7e7d783](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/7e7d78312772c547d9d98c0833421ea6ef47caf6))


### Documentation

* update image format references to PNG ([edbed4f](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/edbed4f187023c530edefcd9a6067eaa79f8ca8b))
* update README for jpeg snapshots and masking elements ([7f7b415](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/7f7b41502bbdb6b733af891ab5c46dc329fc7762))
* update README for visual regression testing ([32b4550](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/32b4550a59408b62af38b61d13a3cbc8cf8c64fd))

## 0.1.0 (2025-03-22)


### Features

* add visual snapshot testing in pytest plugin ([07fdf56](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/07fdf56892b348299fc966af8e3a8a7b76cb791d))
* introduce snapshot and test enhancements ([632f579](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/632f579af5bab38cdca5064b33b6de758715744a))


### Documentation

* add README for visual testing plugin ([79d6440](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/79d6440f7a4bd93bd81a7f35bef2baf130dbb866))
* update configuration instructions in README.md ([458e2ee](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/458e2ee7983f1f7711d454babed3cb978e0faa1e))
* update project description and keywords in pyproject.toml ([8906878](https://github.com/iloveitaly/pytest-playwright-visual-snapshot/commit/89068780c708e1e36c59672a9eab8a6b71da28d1))
