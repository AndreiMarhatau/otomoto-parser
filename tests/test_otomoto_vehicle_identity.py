from otomoto_parser.v1.otomoto_vehicle_identity import (
    decrypt_otomoto_secret,
    extract_otomoto_vehicle_identity_from_html,
)


SAMPLE_HTML = """
<html>
  <head></head>
  <body>
    <script nonce="x" type="application/json" id="__NEXT_DATA__">
      {
        "props": {
          "pageProps": {
            "advert": {
              "id": "6146171299",
              "parametersDict": {
                "vin": {
                  "label": "vin",
                  "values": [
                    {
                      "value": "Wv3K9Zx1k7PjYIaJz62w+Pbg26TSroFd9HO9iVuhxOgs.1.ctzWCzFZf7YcoRbtqWY++A==",
                      "label": "Wv3K9Zx1k7PjYIaJz62w+Pbg26TSroFd9HO9HO9iVuhxOgs.1.ctzWCzFZf7YcoRbtqWY++A=="
                    }
                  ]
                },
                "date_registration": {
                  "label": "date_registration",
                  "values": [
                    {
                      "value": "cH5qTiAf6w1chGVA+eFmkBKi8sphFIb+mzI=.1.oKkuw5QdwFdr/LuW8/+pXg==",
                      "label": "cH5qTiAf6w1chGVA+eFmkBKi8sphFIb+mzI=.1.oKkuw5QdwFdr/LuW8/+pXg=="
                    }
                  ]
                },
                "registration": {
                  "label": "registration",
                  "values": [
                    {
                      "value": "O42JyEHx385vdx5SNhOZSIPPptMpvJWl.1.KRKEiQLPrCHWJtiYviYD7A==",
                      "label": "O42JyEHx385vdx5SNhOZSIPPptMpvJWl.1.KRKEiQLPrCHWJtiYviYD7A=="
                    }
                  ]
                }
              }
            }
          }
        }
      }
    </script>
  </body>
</html>
"""


def test_decrypt_otomoto_secret() -> None:
    assert (
        decrypt_otomoto_secret(
            "Wv3K9Zx1k7PjYIaJz62w+Pbg26TSroFd9HO9iVuhxOgs.1.ctzWCzFZf7YcoRbtqWY++A==",
            "6146171299",
        )
        == "WDDSJ4EB2EN056917"
    )


def test_extract_otomoto_vehicle_identity_from_html() -> None:
    identity = extract_otomoto_vehicle_identity_from_html(SAMPLE_HTML)

    assert identity.advert_id == "6146171299"
    assert identity.vin == "WDDSJ4EB2EN056917"
    assert identity.first_registration_date == "2014-01-01"
    assert identity.registration_number == "DLU8613F"


def test_extract_otomoto_vehicle_identity_from_html_allows_missing_registration_fields() -> None:
    html = """
<html>
  <body>
    <script nonce="x" type="application/json" id="__NEXT_DATA__">
      {
        "props": {
          "pageProps": {
            "advert": {
              "id": "6146171299",
              "parametersDict": {
                "vin": {
                  "label": "vin",
                  "values": [
                    {
                      "value": "Wv3K9Zx1k7PjYIaJz62w+Pbg26TSroFd9HO9iVuhxOgs.1.ctzWCzFZf7YcoRbtqWY++A=="
                    }
                  ]
                }
              }
            }
          }
        }
      }
    </script>
  </body>
</html>
"""

    identity = extract_otomoto_vehicle_identity_from_html(html)

    assert identity.vin == "WDDSJ4EB2EN056917"
    assert identity.first_registration_date is None
    assert identity.registration_number is None
