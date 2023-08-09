from flask import redirect, render_template, request, url_for

from main import app, forms
from main.service import db, exceptions, handlers
from main.tasks import process_urls_from_zip_archive


@app.route("/resources/", methods=["GET"])
def index():
    domain_zone = request.args.get('domain_zone', None)
    resource_id = request.args.get('id', type=int)
    uuid = request.args.get('uuid', None)
    availability = request.args.get('availability', None)
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=10, type=int)

    response = handlers.handle_get_resources_with_filters(
        domain_zone=domain_zone,
        resource_id=resource_id,
        availability=availability,
        page=page,
        per_page=per_page,
        uuid=uuid,
    )

    return render_template('index.html', data=response.dict())


@app.route("/logs/", methods=["GET"])
def get_logs():
    app.logger.info(f"GET - {request.url} visited")
    return render_template("logs.html")


@app.route("/add-resource/", methods=["GET", "POST"])
def add_resource():
    form_text = forms.URLTextForm()
    form_file = forms.URLFileForm()

    if request.method == 'POST':
        # process first form with text
        if form_text.submit_text.data and form_text.validate():
            url = form_text.url.data
            try:
                web_resource = db.create_web_resource(validated_url=url)
                app.logger.info(f"201 - User posted new URL: {url}")
                return redirect(url_for('get_resource_page', resource_uuid=web_resource.uuid))
            except exceptions.AlreadyExistsError:
                form_text.url.errors.append("Такая ссылка уже существует")

        # process second form with file
        if form_file.submit_file.data and form_file.validate():
            file = form_file.file.data
            # create ZipFileProcessingRequest model instance
            processing_request_id = db.create_file_processing_request()
            # create celery task and pass id of created request to it as argument
            process_urls_from_zip_archive.delay(
                zip_file=file.read(),
                request_id=processing_request_id,
            )
            app.logger.info("File processing request created.")
            return redirect(url_for('get_processing_request_page', request_id=processing_request_id))

    return render_template('add_resource.html', form_text=form_text, form_file=form_file)


@app.route("/test_logs/", methods=["GET"])
def test_logs():
    # app.logger.exception("EXCEPTION")
    app.logger.critical("critical")
    app.logger.warning("warning")
    app.logger.debug("debug")
    app.logger.info("info")
    return "<h1>Test log messages for all levels called. Check web log viewer</h1>"


@app.route("/resources/<uuid:resource_uuid>", methods=["GET"])
def get_resource_page(resource_uuid):
    try:
        resource_data = handlers.handle_get_resource_data(resource_uuid)
    except exceptions.NotFoundError:
        return render_template('404.html'), 404

    app.logger.info(f"GET - resource page {request.url} visited")
    return render_template("resource_page.html", resource_data=resource_data)


@app.route("/processing-requests/<int:request_id>", methods=["GET"])
def get_processing_request_page(request_id):
    try:
        status_info = handlers.handle_get_request_status(
            request_id=request_id,
            storage_client=app.extensions["redis"]
        )
        return render_template("request_page.html", resource_data=status_info)
    except exceptions.NotFoundError:
        return render_template('404.html'), 404


@app.route("/feed/", methods=["GET"])
def get_news_feed():
    feed_items = handlers.handle_get_news_feed()
    return render_template("feed.html", feed=feed_items)
