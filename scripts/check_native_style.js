/* Check physical function length and prohibited control-flow in native sources. */
"use strict";
const fs = require("fs");
const path = require("path");
const acorn = require("acorn");
const walk = require("acorn-walk");

function paths(directory) {
    return fs.readdirSync(directory, {withFileTypes: true}).flatMap((entry) => {
        const name = path.join(directory, entry.name);
        return entry.isDirectory() ? paths(name) : (name.endsWith(".js") ? [name] : []);
    });
}

function check(file) {
    const tree = acorn.parse(fs.readFileSync(file, "utf8"), {ecmaVersion: 2020, locations: true});
    const errors = [];
    walk.full(tree, (node) => {
        if (node.type === "BreakStatement" || node.type === "ContinueStatement") {
            errors.push(file + ":" + node.loc.start.line + " prohibited " + node.type);
        }
        if (/^(FunctionDeclaration|FunctionExpression|ArrowFunctionExpression)$/.test(node.type)) {
            const length = node.loc.end.line - node.loc.start.line + 1;
            if (length > 40) errors.push(file + ":" + node.loc.start.line + " function has " + length + " lines");
        }
    });
    return errors;
}

const errors = ["native", "scripts", "tests"].flatMap(paths).flatMap(check);
if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
} else {
    console.log("Native style gate passed.");
}
