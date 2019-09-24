# Copyright (c) 2019 Microsoft Corporation
# Distributed under the MIT software license

# NOTE: This module is highly experimental. Expect changes every version.

import os
from IPython.display import display, HTML
import uuid

from plotly.io import to_json
from plotly import graph_objs as go
import sys
import json
import base64

import logging

log = logging.getLogger(__name__)

this = sys.modules[__name__]
this.jupyter_initialized = False


def _build_error_frame(msg):
    error_template = r"""
    <style>
    .center {{
        position: absolute;
        left: 50%;
        top: 50%;
        -webkit-transform: translate(-50%, -50%);
        transform: translate(-50%, -50%);
    }}
    </style>
    <div class='center'><h1>{}</h1></div>
    """
    html_str = error_template.format(msg)
    return _build_base64_frame_src(html_str)


def _build_base64_frame_src(html_str):
    html_hex64 = base64.b64encode(html_str.encode("utf-8")).decode("ascii")
    return "data:text/html;base64,{}".format(html_hex64)


def _build_viz_figure(visualization):
    if visualization is None:
        _type = "none"
        figure = "null"
    elif isinstance(visualization, go.Figure):
        _type = "plotly"
        figure = json.loads(to_json(visualization))
    elif isinstance(visualization, str):
        _type = "html"
        figure = _build_base64_frame_src(visualization)
    else:
        # NOTE: This error is largely specific to Dash components,
        #       all Dash component visualizations are being replaced with D3 soon.
        _type = "html"
        msg = "This visualization is not yet supported in the cloud environment."
        log.debug("Visualization type cannot render: {}".format(type(visualization)))
        figure = _build_error_frame(msg)

    return {"type": _type, "figure": figure}


def _build_viz_err_obj(err_msg):
    _type = "html"
    figure = _build_error_frame(err_msg)
    viz_figure = {"type": _type, "figure": figure}

    viz_obj = {
        "name": "Error",
        "overall": viz_figure,
        "specific": [],
        "selector": {"columns": [], "data": []},
    }
    return viz_obj


def _build_viz_obj(explanation):
    overall = _build_viz_figure(explanation.visualize())
    if explanation.selector is None:
        # NOTE: Unsure if this should be a list or None in the long term.
        specific = []
        selector_obj = {"columns": [], "data": []}
    else:
        specific = [
            _build_viz_figure(explanation.visualize(i))
            for i in range(len(explanation.selector))
        ]
        selector_obj = {
            "columns": list(explanation.selector.columns),
            "data": explanation.selector.to_dict("records"),
        }

    viz_obj = {
        "name": explanation.name,
        "overall": overall,
        "specific": specific,
        "selector": selector_obj,
    }
    return viz_obj


def _build_javascript(viz_obj, id_str=None, default_key=-1):
    script_path = os.path.dirname(os.path.abspath(__file__))
    js_path = os.path.join(script_path, "..", "lib", "interpret-inline.js")
    with open(js_path, "r", encoding="utf-8") as f:
        show_js = f.read()

    init_js = """
    <script type="text/javascript">
    console.log("Initializing interpret-inline");
    {0}
    </script>
    """.format(
        show_js
    )

    if id_str is None:
        div_id = "_interpret-viz-{0}".format(uuid.uuid4())
    else:
        div_id = id_str

    body_js = """
    <div id="{0}"></div>
    <script type="text/javascript">

    (function universalLoad(root, callback) {{
      if(typeof exports === 'object' && typeof module === 'object') {{
        // CommonJS2
        console.log("CommonJS2");
        var interpretInline = require('interpret-inline');
        callback(interpretInline);
      }} else if(typeof define === 'function' && define.amd) {{
        // AMD
        console.log("AMD");
        require(['interpret-inline'], function(interpretInline) {{
          callback(interpretInline);
        }});
      }} else if(typeof exports === 'object') {{
        // CommonJS
        console.log("CommonJS");
        var interpretInline = require('interpret-inline');
        callback(interpretInline);
      }} else {{
        // Browser
        console.log("Browser");
        callback(root['interpret-inline']);
      }}
    }})(this, function(interpretInline) {{
        console.log(interpretInline);
        interpretInline.RenderApp("{0}", {1}, {2});
    }});

    </script>
    """.format(
        div_id, json.dumps(viz_obj), default_key
    )

    return init_js, body_js


def render(explanation, id_str=None, default_key=-1, detected_envs=None):
    if isinstance(explanation, list):
        msg = "Dashboard not yet supported in cloud environments."
        viz_obj = _build_viz_err_obj(msg)
    else:
        viz_obj = _build_viz_obj(explanation)

    init_js, body_js = _build_javascript(viz_obj, id_str, default_key=default_key)

    final_js = body_js
    if not this.jupyter_initialized:
        final_js = init_js + body_js
        this.jupyter_initialized = True

    if detected_envs is not None and "databricks" in detected_envs:
        # NOTE: If in databricks environment, the following function is globally defined.
        displayHTML(final_js)
    else:
        display(HTML(final_js))