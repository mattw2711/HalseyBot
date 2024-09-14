import logging
import azure.functions as func

from main import check_for_new_products
from usBot import check_for_new_productsUS

app = func.FunctionApp()

@app.schedule(schedule="0 */1 * * * *", arg_name="myTimer", run_on_startup=True,
              use_monitor=False) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    check_for_new_products()
    check_for_new_productsUS()