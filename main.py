from flask import Flask, request, render_template
import openai

app = Flask(__name__)


@app.route('/')
def index():
    """
    index
    :return:    index html
    """
    return render_template("index.html")


@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/features')
def features():
    return render_template("features.html")


@app.route("/upload", methods=['POST'])
def askgpt_upload():
    """
    ask GPT
    :return:    analyzed response from GPT
    """
    openai.api_key = ""
    file = request.files['file']
    print(file)

    contents = file.read().decode("utf-8")
    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"""
            Please analyse this performance test results: \n {contents}
            """,
            temperature=0,
            max_tokens=100,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        return render_template("analysis_response.html", response=response['choices'][0]['text'])
    except Exception as e:
        return e


if __name__ == '__main__':
    app.run(debug=True)
