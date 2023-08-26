import logging
from flask import Flask, request, jsonify
from flask_opentracing import FlaskTracing
from flask_cors import CORS
from jaeger_client import Config
from jaeger_client.metrics.prometheus import PrometheusMetricsFactory
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from prometheus_flask_exporter import PrometheusMetrics
from flask_pymongo import PyMongo
import os


app = Flask(__name__)
CORS(app)
app.config["MONGO_URI"] = "mongodb://example-mongodb-svc.default.svc.cluster.local:27017/example-mongodb"

mongo = PyMongo(app)
JAEGER_HOST = os.getenv("JAEGER_HOST", "localhost")

metrics = PrometheusMetrics(app)
metrics.info("app_info", "Application info", version="1.0.3")
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

def init_tracer(service):
    logging.getLogger("").handlers = []
    logging.basicConfig(format="%(message)s", level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    config = Config(
        config={
            "sampler": {"type": "const", "param": 1},
            "logging": True,
            "local_agent": {
                "reporting_host": JAEGER_HOST
            }
        },
        service_name=service,
        validate=True,
        metrics_factory=PrometheusMetricsFactory(service_name_label=service),
    )

    
    return config.initialize_tracer()

tracer = init_tracer('backend')
tracing = FlaskTracing(tracer, True, app)

@app.route("/")
def homepage():
    response = "Hello World"
    
    with tracer.start_span('homepage') as span:
        span.set_tag('message', response)
        return response


@app.route("/api")
def my_api():
    with tracer.start_span('my-api'):
        answer = "something"
        return jsonify(response=answer)


@app.route("/star", methods=["POST"])
def add_star():
    with tracer.start_span('add star'):
        star = mongo.db.stars
        name = request.json["name"]
        distance = request.json["distance"]
        star_id = star.insert({"name": name, "distance": distance})
        new_star = star.find_one({"_id": star_id})
        output = {"name": new_star["name"], "distance": new_star["distance"]}
        return jsonify({"result": output})

if __name__ == "__main__":
    app.run()

