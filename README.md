# Заключительное тестовое задание в рамках Голодных Игр

Создано REST API на Flask для каталогизации и структурирования информации по различным веб-ресурсам, а также мониторинга их доступности.

Для работы с базой данных использовалась библиотека ```flask-SQLAlchemy``` и ```alembic``` для миграций. Сериализация и валидация данных осуществляется с помощью ```Pydantic```. Эта библиотека, как и сам Flask, для меня новые, поэтому возможно не в полной мере использовала её функционал.

Задачи регулярного мониторинга доступности ресурсов и удаления недоступных ресурсов решены с помощью Celery-Beats, в качестве брокера сообщений используется ```Redis```. Для того чтоб задать критерий удаления, в модель веб-ресурса было добавлено поле для счетчика, который инкрементится при повторной недоступности ресурса или же обнуляется, если ресурс снова становится доступен. Количество раз подряд, когда ресурс был недоступен, после которого ресурс подлежит удалению, задается в файле конфигурации ```config.yaml``` в секции ```MAX_RETRIES```.

Расписание для каждой периодической задачи задается в секции ```PERIODIC_TASKS``` в поле ```RUN_SCHEDULE_HOUR``` (изначально хотела задавать расписание строкой крон-формата, но не нашла как это сделать, поэтому для упрощения задала возможность лишь указывать через какое ```n``` часов прогонять таски).

Функции, которые стучатся в базу данных, вынесены в отдельный файл ```services.py```.

Для организации ротации лог-файлов использовался ```RotatingFileHandler``` из стандартного модуля ```logging```.
___

## Функционал приложения:

   * POST ```/resources``` - отправить ссылку для обработки

        Ожидаемый формат тела запроса:

        ```
        {
            "url": "https://vk.com"
        }
        ```

   * POST ```/resources``` - отправить zip архив с cvs-файлом с ссылками для обработки

        Файл передается с ```content-type multipart/form-data``` в поле с названием ```file```.

   * POST ```/resources/<resource_uuid: int>``` - сохранить скриншот для ссылки с переданным uuid

   * GET ```/resources``` - возвращает все сохраненные ссылки из БД с последним статус-кодом ответа ресурса для каждой ссылки с пагинацией и фильтрацией.

        Пример запроса с квери-параметрами:

        ```/resources?availability=true&id=1&domain_zone=org&page=1per_page=2```



   * GET ```/logs``` - возвращает последние 50 строчек лог-файла (их количество настраивается в конфигурации системы и задается в секции ```MAX_LOG_LINES```)

   * DELETE ```/resources/<resource_id: int>``` - удалить обработанную ссылку


___

## Развертывание в Linux

Точкой входа в приложение является ```main.py``` в корневой директории проекта. Приложение обернуто в docker-compose, как и в прошлый раз для поднятия используется makefile :) Для установки необходимых библиотек и применения миграций используется скрипт ```docker-entrypoint.sh```.

Для развертывания нужно выполнить следующие шаги:

1. Клонировать репозиторий:
   ```
   git clone https://github.com/Dana299/hungergames_part2.git && cd hungergames_part2
   ```
2. Выполнить команду:
   ```
   make build
   ```
3. Для остановки контейнеров выполните:
   ```
   make stop
   ```
   Для удаления контейнеров выполните:
   ```
   make clean
   ```
___
# P.S. Доработки

В Celery задаче для обработки ссылок из файла ответ никак не учитывает дубликаты ссылок (количество дублей в переданном файле и количество ссылок в файле, которые уже есть в бд). Также в идеале наверное стоит распределять обработку ссылок между разными воркерами celery.


