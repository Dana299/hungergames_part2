from flask_wtf import FlaskForm
from wtforms import FileField, StringField, SubmitField
from wtforms.validators import URL


class URLTextForm(FlaskForm):
    url = StringField(
        "url",
        validators=[URL(message="Введенное значение не является ссылкой.")]
    )
    submit_text = SubmitField("Отправить")


class URLFileForm(FlaskForm):
    file = FileField("file", validators=[])
    submit_file = SubmitField("Отправить")
