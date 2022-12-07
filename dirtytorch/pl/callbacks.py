# short_desc: Custom lightning callbacks
from pytorch_lightning.callbacks import Callback
from typing import Callable, Any
from functools import wraps
import torch


class MetricWatcher(Callback):
    def __init__(self,
                 metric_name: str,
                 mode: str = "max",
                 eq: bool = True,
                 getter: Any = None,
                 log_step: bool = False):
        super().__init__()
        assert mode in ["min", "max"]
        self.metric_name = metric_name
        self.best_name = f"best_{metric_name}"
        self.step_name = f"step_{metric_name}"
        self.best_step_name = f"best_step_{metric_name}"
        self.mode = mode
        self.eq = eq
        self.getter = getter
        self.log_step = log_step

        if mode == "min":
            self.current_best = torch.inf
            self.current_best_step = torch.inf
        else:
            self.current_best = -torch.inf
            self.current_best_step = -torch.inf

    def on_validation_epoch_start(self, *a, **kw):
        self.metrics = []

    def on_validation_batch_end(self, _, plmodule, outputs, *a, **k):
        if callable(self.getter):
            value = self.getter(outputs)
        elif self.getter is not None:
            value = outputs[self.getter]
        else:
            value = outputs
        self.metrics.append(value)

        if not self.log_step:
            return

        if self.check_surpass(value, self.current_best_step):
            self.current_best_step = value
        plmodule.log(self.step_name, value)
        plmodule.log(self.best_step_name, self.current_best_step)

    def check_surpass(self, value, current_best):
        if self.mode == "min":
            surpass = value < current_best
        else:
            surpass = value > current_best
        if self.eq:
            surpass = surpass or value == current_best
        return surpass

    def on_validation_epoch_end(self, _, plmodule):
        n = len(self.metrics)
        if n == 0:
            return
        mean_metric = sum(self.metrics) / n
        if self.check_surpass(mean_metric, self.current_best):
            self.current_best = mean_metric
        plmodule.log(self.metric_name, mean_metric)
        plmodule.log(self.best_name, self.current_best)


class GlobalStepLRScheduler(Callback):
    def __init__(self, every: int = None, only=True):
        super().__init__()
        self.every = every
        self.only = only

    def on_before_optimizer_step(self,
                                 trainer,
                                 pl_module,
                                 optimizer,
                                 optimizer_idx):
        global_step = trainer.global_step

        if global_step != 0 and global_step % self.every == 0:
            for lrs in trainer.lr_scheduler_configs:
                lr_scheduler = lrs.scheduler
                lr_scheduler.step()
                for lr in lr_scheduler.get_lr():
                    pl_module.log("learning_rate", lr)

    def on_train_start(self, trainer, model):
        # Co-exist with the original config
        if not self.only:
            return

        # Disable calling lr scheduler from the model
        for lrs in trainer.lr_scheduler_configs:
            lrs.interval = 'epoch'
            lrs.frequency = 99999999999999999


class MetricCallback(Callback):
    def __init__(self,
                 metric: str,
                 mode: str,
                 callback: Callable,
                 on: str, model=None):
        super().__init__()
        assert mode in ["min", "max"]
        assert on.startswith("on_") and hasattr(Callback, on)

        # Every hook receive trainer as first argument
        @wraps(getattr(self, on))
        def callback_wrapper(trainer, *args, **kwargs):
            current_metric = trainer.logged_metrics[self.metric]
            if self.mode == "min":
                cond = current_metric < self.current_metric
            elif self.mode == "max":
                cond = current_metric > self.current_metric
            if cond:
                self.current_metric = current_metric
                self.callback(self, *args, **kwargs)

        setattr(self, on, callback_wrapper)
        if mode == "min":
            self.current_metric = torch.inf
        elif mode == "max":
            self.current_metric = -torch.inf
        self.callback = callback
        self.metric = metric
        self.mode = mode
        self.model = model
        self.on = on

    def __repr__(self):
        name = self.__class__.__name__
        args = [
            f"metric={self.metric}",
            f"mode={self.mode}",
            f"on={self.on}",
        ]
        args = ', '.join(args)
        return f"{name}({args})"
