function is_gmp() {
    document.getElementById("step_gmp_dev").style.display = "block";
}

function no_gmp() {
    document.getElementById("step_no_gmp_dev").style.display = "block";
}

function no_gmp_but_deviation() {
    document.getElementById("step_no_gmp_dev").style.display = "block";
    document.getElementById("step_no_gmp_safety").style.display = "block";
}

function gmp_deviation() {
    document.getElementById("step_gmp_dev").style.display = "block";
    document.getElementById("step_gmp_safety").style.display = "block";
}

function gmp_no_deviation() {
    document.getElementById("step_gmp_dev").style.display = "block";
    document.getElementById("step_gmp_oos").style.display = "block";
}
