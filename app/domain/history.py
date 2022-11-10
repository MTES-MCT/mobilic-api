from typing import NamedTuple
from datetime import datetime
from enum import Enum

from app.models import (
    User,
    Activity,
    MissionValidation,
    LocationEntry,
    Expenditure,
)
from app.models.activity import ActivityType
from app.models.event import Dismissable
from app.models.location_entry import LocationEntryType
from app.templates.filters import (
    format_expenditure_label,
    format_activity_type,
    format_time,
)


class LogActionType(int, Enum):
    DELETE = 1
    UPDATE = 2
    CREATE = 3


class Picto(str, Enum):
    ACTIVITY_DRIVE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAMAAABHPGVmAAAAAXNSR0IB2cksfwAAAAlwSFlzAAALEwAACxMBAJqcGAAAALRQTFRFa+Zw////kOyUtfO3femC3/rg5fvmqvGtwvXE9P306Pvpbudz1vjYdOh5p/CqxfXG7vzu8f3xieuNsPKyced2le2Zg+qHoe+kvPS+mO6cnu+hhuuKv/TBj+yT4fripfCp6vvr0/jV2vnbrfGweOh8hOqI0ffS5vvncud3x/bJvvTA9v32duh7+f75/f/9ufO8k+2X7/zwjuySl+2azfbO3fnei+uPgOmEu/S9eeh+nO6g0vfUM2wlSwAAA3RJREFUeJy9mul6ojAUhk+UXVxQa9VatYu1+77NzP3f1xAJLco5IUDI9w8SeJ+EkLMFmKKicOHOhla3A9DpWsOZuwgj1WdBpVPgzS1AZM29QA/EHk0wQKrJyK4L8acnMkKik6lfA+L0igmJek5FiHOsiuA6lmBIiO+WQXC55KRREK9blgHQ9UpBgqPyCK4jfEWjkH6nGiP+T/uqEOU1hamnBBmc1mEAnA6KITa6gZSRldsCDiHhuC4DYBzKIWf1EVxnMkiohwEQ0hBbw1wlGtsUZFD7m//KGhCQmmt3X6c4pNY/mFcPg/T1MgD6eUhQeb+i1AlykIr7rkxHhxBPPwPA24f4FWxUsbr+HqS0rVWTm4U4zTAAnAyklF9SRse/kMYGIoYCDfzrWfVSiJ9vs1oyff5Rp/gCMj1suEd9jqwulCFTAcn51IUMxpStwkkCsXMN62LISnko9g4yyt0vZrC2MmS0g+RjHK2QCYcE+ftaIRDEEGT/1QvxYsi8acg8hiCLUQlyff6xdIJBdPfwuO63JBCLQYTcVoK09q5llAgwp7EChN3TkBAWmiAPNGQBmE2sAmHnJMSFmS4Ie6IgMxhqg5D72RCw7bQihL3hEAswX6gq5BGbltgzAsw7rQphS9Rk4g5wZQj7h0+YXkjelJNjqQF5QRE6PzwX8rqu1iVMQCydPyMFGWrcVkjITN8GSUNcbVu9BLIoMlqRjXt6Wcjg/EUKCQvML5/Mt3wCKwtZ85D2QgaJ5I5EYrmfZZC7JB8zoiEW7hLdige24vpMAklzDHfJ5Uf+bXPcuZuJHE/ahKRiVynkr+izzI59Tx7upgLwUGf7Y7Zv4o9zGAjB+KLdbv+662vmt9vuBnlXgDvcieI3JM9cOuyK6PORxptvjN3iXSZE6JDoM55h7k1NrmjfbSUc1ud4Bb7iXUZEECQUz9LDd+s7jvreqS78Uyyf5u/x17ghethEOCd0vZQsfqHNVnShJlSEc4Q141rtlpk0Ct3c8tJWQKYb0sAUCbF/dPn6dS1j7PoMv+jGNMQ2kiwwk/YwksAxk4oyklQzkx40kug0k7I1k3w2kkY3UxAwU9owU6QxUm4yUzgzUwI0U8w0U5Y1U2BmRkrlzEzR38zxBWbkIAYzc6SEGTkcs8M0f8yHy8CBpZ2aP3qVqPlDZEJ1jsP9B1flMA4vhQm1AAAAAElFTkSuQmCC"
    ACTIVITY_WORK = "data:image/png;base64,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"
    ACTIVITY_SUPPORT = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAMAAABHPGVmAAAAAXNSR0IB2cksfwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAOpQTFRFIZNY////9/n6VqyBjMapPKBtIpNYL5pjJpVcz+jb3O7le7+c7vfyo9K62OziwuHRf8Gfp9S9ntC2Sqd3KphfbriSZbSLcrqVTql6V62BiMWm6vXvRaVzYLKIms6z5fLs2OrjzOXaX7GHyePXvd/OM5tmx+LW3e3nlsuxRaRz4+/rotC5wd/RfsCe6fLv0efd0+jfNZ1nd7yZLJhgdbuYtNnHksmuhMKjmcyzUKl7er2bW66EgcGi9Pf41unhU6t9t9vKP6Fv3+7opNK77vTzQqNx6/PxrdbC7/X0s9nG5/HuaLWOv97QsNfEApi5pwAAA4hJREFUeJy92ud6okAUBuDjKCIIYo/R2Da9955s6vbd+7+dBRkTlXOGAcb5flkG3oc2TIOcZHpevdruGGapWCyZRqddrXs92W1BppDttgxAYrRcWw1iddcwYJq1rpUVcQYNkRCmMXAyIJVyMZ4IUixXUiKVFTkhzIqAIRGnmoQIUiVPGoW4ZlIDwHQTIXY/ORGkj9/RKFIrpTMASjVZpJyWCFKWQoarWQyA1WE8YqEVSJIYkSpgEfGaWQ2ApidGNiQfcXGKGyLEU2L4ikcjloJzFaZpUcgw8zX/jDEkkIz37nxWcSTTMxhNGUNqag2AWhSxU9dXVEp2BElZ74rSX0Rc9QaAO484Kd5R8TGdOSTxu1Yu1VmkshwDoDKDJGqXJMnKJ7K0A+GHAkt41mdTniJOtII38qLcnkojRYcjg8V/Nl0Wk0NpZcCRSJt6P85gTPqt0AgRK/LHKB45kz4Ua4J0I7/HG6wgjXQnSLSPoxRZCxA7+rtSBGwfQepftYjrI61lIy0fQW5GKeT8YGt8/HV77+j9cbSfFyBGDnrIz1JIfu67SOmBpwZhmzTiQV0R8k4jdcDeiWkQ9pdEqtBWhbArCmlDRxnCLgikA1h1mhJhX3DEAKwtlBZ5xAdiTMBap2kRNkZfmSXA+lapEfaMIUXFCNtBEaWni7FX9HSpvPBBkN2ZSm9hAjFUPowU0lFYrZBIW10FSSNVZVW9AKnHvbT21vGW3iyyffAqRLyY12/Q5u1vC5FRUC0eipCeuCERvrnvRcj3cDzmmkYMvEl0wzc44d+fBcgbL3MUft2K7q2FN+7a6+EW05uiHkUupsgfXmY8e+xzcfFmKkDQ1TlhB/zbG2N3ix0haD4UCgXGrnmZETsqFO52kX3ZeIM7jL+HcJvTY3ZJlNlix+GHPl4BA29wI12HMLf+GQ6qz2+XdNvtjDdY7/078Akv0iU6QTw1xn7u5Hd+M/aPKhJcivWr1g//alCjTBbRneM5Hwtufp7dE17kF1GgQXVMP3I2uc0eaMNXbvb8Il/J4YYB3cX+yObTy7nImJRpvJD/fXSxtQwW6Bn20DKAo2coSsugmp7hQS0DnXqGbPUMPmsZRtczIaBnakPPJI2W6SY9E2d6pgD1TGbqmZbVM8Gc0zJVntMz6a9n+UJOy0KMnJ4lJTkti2MmzPKX+QTRsGBpkuUvvQqz/EVkPFmWw/0HPu8/dxUkT9YAAAAASUVORK5CYII="
    ACTIVITY_TRANSFER = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAMAAABHPGVmAAAAAXNSR0IB2cksfwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAIRQTFRFQX3E////oL7i0N/wcZ7TcJ3TWI3LoL7hTYXIRYDFjrLcsMnn8PX61uPy4ev2y9vvkrTd3uj1rMbl8/f7lLbe6fD4uM/pb53Se6XWqcTkYJLOg6rYtMzod6LVhqzaSYPHmbnfZJXP7fL5aJjQia7a2+f0ZZXPx9nu5+/4z97wfabXxNft8i/WqgAAA0ZJREFUeJy9mtdiwjAMRWUKaYAMCNAyy6br//+vGaRAciVsYnxfPQ4OtqxhUpraxclguvf8LlHX9/bTQRLvdMeSTqeov/AIyFv0IzuQcDNHgFLzTdgUEsy2EqHQdhY0gAx79wmFesMHIcMPXUSmDwHDQoKBCSLTgP1oHKTvmzKI/L4RJFqZIzKt8I6GkGX3MUZ6Tpe6EO09hdTTgkzemzCI3if3ISE0ICbyaiagConXTRlE61iGfDZHZPqUILEdBlHMQ0IL36rQOuQgk8b/+UXehIE03Lu3eseQRmewrh6CLO0yiJZ1SPSwveLUjWoQ1u52OuNXQYfOiRu5qkL6uF/7baTu6ithtmV5v5whAbyj/O/7hEKvEOIHNxB41540VlHqCH/l4BoybMrgKMMrCPJL/C8ThlJvCPJxgcCFJGYMpdrsUnIIOuueKUN9I0ivhASodWwMUXAjB2fIDDW+mEPGaJ7ZGQJ9anOG+kXzbAtIiNoegbzAicIcsuEhx7amBMgmh+AYRxhm1nueQSLjYYa9oxTC2F97kH4KWTwbskghzF1gD+Ip2j0wzLD3jjin0SIkpuT5kIS4+NMiZEDT50OmtJeGHTuaEiF74pxsawYy3cPExesWIT5x3qlFCO8AW4Twsgpx8rmc/PFOtrB4GOv6av0cuHCCP4yiWampcK38NyPIVDaQVR3KVkjhDaRo6tlZfPTFeFMvXlrcQvBS+EtLvH4rugpBWwaQnexIVHTVFTn9vCMhukQV/VyaUYgkuESSc1fRJWKDsZ7g3ElualX/ERv6SyQ3VXK4qxqdKTgMExxutdGHpF9s2umMj7hNCh2cBEE4nGN+rSRoPLZKCEwP5hB44srAFIbY5uEvDH7/Q2ycGPTNUhIjzPhPFuC0B9GpletXnjzJOx2Ya/yS9oAJnFLtO8kinB466yqBwy0l0/0NMGLzg7epKJxUy4Qv2grlwI2+Saox6UHt/CDODlbTg4wtbusx0mmgKolOJmXrtTQFGbWUrZvks5M0upuCgJvShpsijZNyk5vCmZsSoJtippuyrJsCs3JSKlduiv5uni8oJw8xlJsnJcrJ45gc8/xnPpkcPFjK9fynV4We/4jsrCbP4f4Abk4w/aCuSqsAAAAASUVORK5CYII="
    EXPENDITURE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAMAAABHPGVmAAAAAXNSR0IB2cksfwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAI1QTFRFMoT/////9/n6lb/8lL796/L6S5P/Y6H+Pov/M4T/hbb/qsz/ibj/2+n/N4f/7/b/3+z/x93/0+T/P4z/ocb8V5r+xtz7cKn93+v7S5P+rc38fLD9VJj/O4n/ea7/bKf/6/P/5/H/kb3/WJv/osf/psn/XJ3/rs7/fbH/cKn/ZKL/ibf90uP7wtv/utT81WAQdwAAAxBJREFUeJy9mtmCqjAMhoMgiICs477vy8x5/8c7IKCipASK+e+U4mehSbMUFKLW/sG+HPVwYJqDUD9e7IO/pt4LlEGetdShRPrS8tqBBNt5GSDXfBvIQtz9TkRItdu7EhCnb1YjEpl9pyHEOdMIqc4CDApx7TqIRDb60DCIFdZlAIRWLYi3qo9ItCpf0aWQ06AZA2BwokL6TRGJ+iTI5irDALhuqiFBqQOpI/3DBbxD/IUsA2DhiyF/8ohEfyKI3w4DwMchQQvPKtUiwCAb6Xf+lL5BIJJrt6hrOUTKBj/VL4Oc2mUAnD4hXmN/hWngfUAa+l2RVu8Qq30GgFWEuA32qGqFbgFSe6+lyX6FON9hADgvkFpxSayJYWjazTAmVQPPT0itifRm03En13g6Eo92HpAatj6Jup2iulpPML6fQ1xinBjPIuqUSIQx3QyypzJG77N4YAz0nn0GIcTUd5VOI5OG3bRLIQEN0ZsW/vtwOCx8RhdacIdsaZB/zx+MjPQl9EZRttC6P+h92ztEmOM89JjHeFb4fjYWM2CeQDwSQ80Z6selSMgA8GIIyf9ORMvIEDJiXwzKkgIZVj56XMsYQglRZhIM0BVYU8b9ppBZ9cgyrYESNBopY9iMESMO+MWRlimbyFQr6kaEHADfE3uYp8JXc7lsuKDX1ApGV+TiX3WB49cnEiPQFdzaRGIEGgvd1FzplIZqURX77otCIESn6T/H96UqDYCw9cpCTB4Iy+MSBMG5xWcvXnsX1eJDfAm3Zyg6boztGcoRdyvtWfwFd5DtWbyNu/qnxau5q29o8QeeTWtNGSa7/bIEEjwhEUtwRwtTb/nK/cwRKGEqS8AtlTpMqalD0yTot/C5IglqJZ1DHdmOMzGVTrFVQootWSwQIF6KBTJlj4hc9mhSwFHVmgUcnlIUS1GNpzzIUujkKdnyFJ9Zyug8DQGe1gZPk4al3cTTOONpAfI0M3nasjwNZoWlVa7wNP15ji8oLAcxFJ4jJQrL4Zg75vvHfBIxHFi66/tHr1J9/xBZJpnjcP8B1dM2BMNEr7UAAAAASUVORK5CYII="
    MODIFICATION = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAMAAABHPGVmAAAAAXNSR0IB2cksfwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAHJQTFRF7WwC////9/n67nUS9d7L9d/M734h74cx7WwD8rN+/OXS9Kho+MKW7W8I9vDq/vTs+9/I/OjX+te59apt8aFf8ZBA8pZK9bB4/e7h859Z8Yo28IQr7nIN+MWb/fHn97+R8plP9KJe97yM+tS08apv87uNNmCgagAAAspJREFUeJy92ud66yAMBmA5bh2v1Ct7J+25/1s8eMTxEmBB9P12n/epY0AIwNHMNb8V96Pnrnx/5XrHe3HLr7p/CzoPZfHBg4l4hzizg6S70xTwymmXmiLJcykT6iyfiQESRr6aKONHIREJH3pCnYeEQZGkmEOUKdCXhiGxO9cAcONZSLadT5TZTn/Rk8hlRTMAVhddJKISZSItZL8xMQA2ezWSTk4gc+KNpoAhkp9NDYBzLkd+NYe4PP6vDMmtGELJcSS18K7qnFMM2Rv/5u94ewQx/Hb72UwjRmNwnGgKudg1AC5jJCPPV1hW2QghzruybIdIbN8AiPtIQlij1HGTHjJ7rdVL0UXCzxgAYQeZVZd04/79kxZmjzdC/kfcr8XiR6qELUId66WhUKIXkhAn+NqQK37SIE8zQ648G0Sjpp5Ka0iVZY2kNAPWCy0lrZAdEekr6IK3qxDpHgeJuxwqf9ijpxLJKMbXz1BZow9nAiHMv+8x2Crf+NOxQA4kY6B8S2bxg0Bmlyj9MbhWGeA5cKUaHUVqgCBystEqCkMQN7qhmoFfucG8NbFvaCoF3E0MPeUORyND9ZtXOcKML5hoCEK/FqIagtCuTsmGIHSXXrohCE3EwBCE3usyMQSh99OZGILQ+YTNDEFoDEZDQxD3jxuCUE6QxoYgVFO9uSEIxaJlwRCEfPm1YQhCWkhYMTx5SWTFqEoivLizY1TFHV6mBlaMqkzFC+4RQjJO8q3DECEZzdYB3QQFNoxmE4Ru5wIbxlKxMQ0sGO3GFNtiBxaMdouNNQsCc+PdLMDaHoG50Wl7IA2cTfAK2eg0cHhaUSxNNZ72IEujk6dly9N8Zmmj8xwI8Bxt8BzSsBw38Ryc8RwB8hxm8hzL8hwwOyxH5Q7PoT/P9QWH5SKGw3OlxGG5HFMxn7/mU4bhwlKVz1+9qvP5S2RNTK7D/QeluygRmKSAtgAAAABJRU5ErkJggg=="
    SUPPRESSION = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAMAAABHPGVmAAAAAXNSR0IB2cksfwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAGxQTFRF7WwC////9/n674cx9vDq9vHr7nUS734h7WwD+9/I7W8I9Kho/OXS+MKW/OjX/vTs+ta59d/M8pZK97yM8IQr8Yo2859Z9apu/e7h/fHn9bB48ZBA7nIN+MWb9apt9KJe8plP97+R8Icx+tS0kW+MjAAAAs5JREFUeJy92td2gzAMBmABCTOMZu/5/u9YE+AAwcISQ/9t3fO1gOUJFjGn7HV47jw39P3Q9XbPwys7UX8XKI2SeO+BJt4+TqZBgvNWB1TZnoOxSLp59wlF3pt0BLKKfDORx49WA5HVgyYUefQwKJLeOUSeO/rQMCR2uQaAG7OQZM0n8qz1X7QWuYXDDIDwRkWioUSeiIQcL2MMgMvRjATaAsKJ1ykBv0h2HWsAXLN+5EPs4v3xP31INomhlAxHggmeVZFrgCHH0e+8jndEkJHfbjsXPTKqD3YT6ZDbtAbArYskg+sVljDpIAPrbl/Wv0g8vQEQt5F0wBhljpu2EPZYS8u9iazmMQBWDYQ1L+HkUSOz/SPlvwIz9PVmogpJJyrwuvhpiWzmMwA2JWKaU7sO/jPH1MHeBRKYjL8FqjiLP5MSfJGzybBtTHEWtm1Szl+kd43zNTAlN4zKNkeS/j/EWdqYUhj2sueV5UkUYqq/qEI0VC0Ga29ogylUA/YKMU9RtArZAM+Ck7GRVqEboIiM0KqrcAxFvCjNfhWWoYgDqV1b4RmKeNIaNhWmoYgdsWWtcA1F0CfZlcI1FMGYC5UK11AEZ3ZaKxxDEayht1JYhiJ4SPE+0PEFQ1iPa1E9LpYSsl78on7xHMXlfMLlt4uPYkg8Rmes+kfPWKnPjl5W6j7IVZ7kAtns50zlQC317VrCU17EQeu3XrGUjDb8dmsiRzmRJhK6uktXPNKUSF/bycqeMrnDxg+qEhOmqfgYRVQS6oRbX9sLhTLhpiwdsPEjV2hLB/MiCB+jnCVxESSynJNZmIossUU2C2S2PUQ2cGS2okQ21WS2B0U2OmW2bGU2n0W20WUOBGSONmQOaUSOm2QOzmSOAGUOM2WOZWUOmC2Ro3JL5tBf5vqCJXIRw5K5UmKJXI75MvNf88kjcGHpm/mvXhWZ/xJZmTHX4f4B11gk8d3TNxUAAAAASUVORK5CYII="
    LOCATION = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAMAAABHPGVmAAAAAXNSR0IB2cksfwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAIdQTFRFMoT/////9/n6S5P/lb/8N4f/2+n/Y6H+hbb/ibj/7/b/6/L6qsz/x93/0+T/3+z/M4T/P4z/fLD9xtz7Pov/0+P7S5P+ibf9V5r+ea7/VJj/psn/5/H/bKf/osf/kb3/rs38WJv/O4n/XJ3/6/P/rs7/fbH/ZKL/cKn/cKn9udT83+v7wtv/y2xkywAAA59JREFUeJy9mtl6gjAQhYfgimyKVq1Wba2tXd7/+UpYNEDgDGBzLvmS/CSTTGaSkMXUu7ebXs/2fBiGw7l9vk533ju3LnEKBe7WJo3srRs8BuIfn3WAXM9Hvy/EObw2EVK9HpwekNEkxAipcDLqCBl98AipPhowtRBn2gYhNa0dtDqIO2/LIJq7rSDBS3uE1It+Rmshl2E3BtHwwoVMuiKkJizI/rMPg+hzjyG+1oG0kV1xAWWI99aXQfTmNUN++yOkfpsg3mMYRF49xH/AWKV68+sg+942v8ve10B6zt2iPvWQXmuwqokOcnksg+hShQSd/VWdhkEF0tHvNumlDHEfzyByixCnwx6FNXcKEN5eu1ycopUQq+i0WLIqTFXIiFNj/C0UfY85dUYKhBGXbCJRUvSEa33cIYyOLMoIqQWzK8Rb6ycdQ4gTrDjJIQ6ME7/1jNgyqGboZJADKjmoYwgxQHUPGQTF1F/1DCG+QOXXFOKDYstZE+QHrRg/gRxBqYbB4gzYMYE05jioI0LMQFeeJSQAf1JcIav1eLxeFT6h1RLEEOR/1ek7yxpcqL1D09iNIVtQRv3pm78aq19BA9sYAkIUtTnFxgMdWi/bonfwHypE8YhPfEiMQEHjWjG6+l0x/ho04dEOlFDGJVK/K54frZQdoT1xgHuCIFO6ghKq4+pokyudQQnG7NqAJs4Eg2yh++c26yRGwFhI3du1Kz5qrh9HRgSj07X60zrfhWZwjIBb70YAwaAlxBD6aWb8wAZCPFyl8aoIx0VDbHiwa6E9i6ThGXliTdCV6oTr23AxUnF1V8SIVc/QrUg1dOXEqH6FDlKqviszRkdiBHL1iWqjIhhASu3gppWoboIxphbJTQttv6m0mQMrdyC5/aJAIlMlBZKCrjGRzQiJUmk9GNpIUm0ZwV0mje1ZVk+DOxSm5lqVGStcJ1HACLhzVQaMN1hpwA1Th1ylAWMOVpY6oCTopsIM480sypMgmM7lelKWJG8Z0i2dw4lpLiUGQ6niTQd2ip1r0NYg9xS7xcFg1NIg98MC3vlNomUSVcCM9677sQfnACfTJjb+jLlCqHCA06Ir0vhsoxePopiHaokWPP+eqHCoZuZ40MhBp5kjWzOHz0aO0c1cCJi52jBzSWPkusnMxZmZK0Azl5lmrmXNXDBbRq7KLTOX/maeL1hGHmJYZp6UWEYexySY/3/mI2XgwVKi/396ler/H5Fl6vMc7g/GPTOaSP9mdgAAAABJRU5ErkJggg=="
    VALIDATION = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAMAAABHPGVmAAAAAXNSR0IB2cksfwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAHhQTFRFLn0y////9/n6mL+ck7uWL30zSI1LqMmq0uPT2ujbg7KF7/XvM4A33uvfO4U/xdvHh7SJpMamYZ1kj7mRjbeQeqx95/DnUJJUbqVwN4M7WZhcdqp5aaJsrMyuVJVY6/LroMSiwdnCn8OiibWNg7KHWZhdw9nGXZpg6BhrdAAAAqBJREFUeJy92td2qzAQBdABQq827j3l3vz/H2YoXjFBCGmE5ryGaC8wSKMCjmLu5ao6nIIi8/2sCE6HalXeVf8XVC7Kw3MAggTnMF8Gieq9CHhmX0emSPq4yYQut0dqgMSJP0808ZOYiMRbNaHLVsJMImmlQzSpJh/aFBIWugZAEWoh+UWfaHIRv9FC5JrRDIDsqookVKJJooTs1iYGwHo3j0TCDkQnwagL+IuUR1MD4FjKkXfFT1we/12GlIsYqJTTSLTAs+pyjKaQnfFv/ptgN4EYvrvDrMWI0Tc4TiJCrssaANcxkpP7q6lk+Qgh9ruyXP4i4fIGQDhEUsIYNZ8iHSDaY61aqlcktmMAxC+IVl2ik+0vYu1G+lsBC9/6a5Inki7UwYvipz3ysGcAPHpEoaam59YhkU0DIGqR2rgd71Pyx7pFpHMcJcN1Jcq+QfIFDKmSI2La/7aG635PXhAicl7EeJu+4oyIWYkyb0DgwN22AUiU1g0kVtYNJAzGREUDiYN1A4mTdQMJ6husbiBBrIU0DCRo1amOgQRp6NUykJhBvkTfkZ6BhPxxfbnuWNE0kJD+8J9NYx+GBhKyV/hf19xQ0TaQkH6Mm7GibyAh71ZGCsFAYqaD7BXPwEBirqsfKCQDidlB60WhGUjMD7+bZ9NEAwmFQqLuGv9PNAK1kqi/F5rRlkQqxd3GwGiLO6Uy9Y1utGWqWsHtkY29xtTBIxr91EFxEuTRjH4SpDqdo6253TgnpixTbJbFAp5lD5YFHJ6lKJZFNZ7lQZaFTp4lW57FZ5ZldJ4NAZ6tDZ5NGpbtJp6NM54tQJ7NTJ5tWZ4NZodlq9zh2fTnOb7gsBzEcHiOlDgsh2Naxv4xnyYMB5ba2D961cX+IbI+JsfhfgBlqCGe+vgzUwAAAABJRU5ErkJggg=="


class LogAction(NamedTuple):
    time: datetime
    submitter: User
    submitter_has_admin_rights: bool
    is_after_employee_validation: bool
    resource: any
    type: LogActionType
    version: any = None

    @property
    def is_validation(self):
        return (
            type(self.resource) is MissionValidation
            and self.type == LogActionType.CREATE
        )

    def picto(self):
        if self.is_validation:
            return Picto.VALIDATION
        elif self.type == LogActionType.DELETE:
            return Picto.SUPPRESSION
        elif self.type == LogActionType.UPDATE:
            return Picto.MODIFICATION
        elif type(self.resource) is LocationEntry:
            return Picto.LOCATION
        elif type(self.resource) is Expenditure:
            return Picto.EXPENDITURE
        elif type(self.resource) is Activity:
            if self.resource.type == ActivityType.WORK:
                return Picto.ACTIVITY_WORK
            elif self.resource.type == ActivityType.DRIVE:
                return Picto.ACTIVITY_DRIVE
            elif self.resource.type == ActivityType.SUPPORT:
                return Picto.ACTIVITY_SUPPORT
            elif self.resource.type == ActivityType.TRANSFER:
                return Picto.ACTIVITY_TRANSFER
        return Picto.MODIFICATION

    def text(self, show_dates):
        if self.is_validation:
            return "a validé la mission"

        if type(self.resource) is LocationEntry:
            # Only creations
            return f"a renseigné le lieu de {'début' if self.resource.type == LocationEntryType.MISSION_START_LOCATION else 'fin'} de service : {self.resource.address.format()}"

        if type(self.resource) is Expenditure:
            return f"a {'ajouté' if self.type == LogActionType.CREATE else 'supprimé'} le frais {format_expenditure_label(self.resource.type)}"

        if type(self.resource) is Activity:
            if self.type == LogActionType.CREATE:
                if self.version.end_time:
                    return f"a ajouté l'activité {format_activity_type(self.resource.type)} du {format_time(self.version.start_time, True)} au {format_time(self.version.end_time, True)}"
                return f"s'est mis en {format_activity_type(self.resource.type)} le {format_time(self.version.start_time, True)}"

            if self.type == LogActionType.DELETE:
                if self.resource.end_time:
                    return f"a supprimé l'activité {format_activity_type(self.resource.type)} du {format_time(self.resource.start_time, True)} au {format_time(self.resource.end_time, True)}"
                return f"a supprimé l'activité {format_activity_type(self.resource.type)} démarrée le {format_time(self.resource.start_time, True)}"

            previous_version = self.version.previous_version
            if not self.version.end_time and not previous_version.end_time:
                return f"a décalé le début de l'activité {format_activity_type(self.resource.type)} du {format_time(previous_version.start_time, True)} au {format_time(self.version.start_time, True)}"
            if not self.version.end_time and previous_version.end_time:
                return f"a repris l'activité {format_activity_type(self.resource.type)}"
            if self.version.end_time and not previous_version.end_time:
                return f"a mis fin à l'activité {format_activity_type(self.resource.type)} le {format_time(self.version.end_time, True)}"
            return f"a modifié la période de l'activité {format_activity_type(self.resource.type)} de {format_time(previous_version.start_time, True)} - {format_time(previous_version.end_time, True)} à {format_time(self.version.start_time, True)} - {format_time(self.version.end_time, True)}"


def actions_history(
    mission,
    user,
    show_history_before_employee_validation=True,
    max_reception_time=None,
):
    activities_for_user = mission.activities_for(
        user,
        include_dismissed_activities=True,
        max_reception_time=max_reception_time,
    )
    expenditures_for_user = mission.expenditures_for(
        user,
        include_dismissed_expenditures=True,
        max_reception_time=max_reception_time,
    )
    mission_validations = mission.validations_for(
        user, max_reception_time=max_reception_time
    )

    relevant_resources = [
        mission.start_location,
        mission.end_location_at(max_reception_time),
        *activities_for_user,
        *expenditures_for_user,
        *mission_validations,
    ]

    user_validation = mission.validation_of(user, max_reception_time)

    actions = []
    for resource in relevant_resources:
        if resource is not None:
            actions.append(
                LogAction(
                    time=resource.reception_time,
                    submitter=resource.submitter,
                    submitter_has_admin_rights=resource.submitter.has_admin_rights(
                        mission.company_id
                    ),
                    resource=resource,
                    type=LogActionType.CREATE,
                    is_after_employee_validation=user_validation.reception_time
                    < resource.reception_time
                    if user_validation
                    else False,
                    version=resource.version_at(resource.reception_time)
                    if type(resource) is Activity
                    else None,
                )
            )

            if isinstance(resource, Dismissable) and resource.dismissed_at:
                actions.append(
                    LogAction(
                        time=resource.dismissed_at,
                        submitter=resource.dismiss_author,
                        submitter_has_admin_rights=resource.dismiss_author.has_admin_rights(
                            mission.company_id
                        ),
                        resource=resource,
                        type=LogActionType.DELETE,
                        is_after_employee_validation=user_validation.reception_time
                        < resource.dismissed_at
                        if user_validation
                        else False,
                    )
                )

            if isinstance(resource, Activity):
                revisions = [
                    v
                    for v in resource.retrieve_all_versions(
                        max_reception_time=max_reception_time
                    )
                    if v.version_number > 1
                ]
                for revision in revisions:
                    actions.append(
                        LogAction(
                            time=revision.reception_time,
                            submitter=revision.submitter,
                            submitter_has_admin_rights=revision.submitter.has_admin_rights(
                                mission.company_id
                            ),
                            resource=resource,
                            type=LogActionType.UPDATE,
                            is_after_employee_validation=user_validation.reception_time
                            < revision.reception_time
                            if user_validation
                            else False,
                            version=revision,
                        )
                    )

    if not show_history_before_employee_validation:
        actions = [a for a in actions if a.is_after_employee_validation]
    return sorted(actions, key=lambda a: (a.time, a.type))
