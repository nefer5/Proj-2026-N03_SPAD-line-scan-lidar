"""Shared input schema and spectral evaluator for basic, CSV and manual modes."""
from copy import deepcopy
from typing import Literal
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.interpolate import PchipInterpolator
from scipy.special import erf
from .configuration import Algorithms


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wavelength_nm: float = Field(gt=0)
    value: float = Field(ge=0)


class BasicCurve(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    shape: Literal["constant","rectangle","gaussian","cosine_flat"]
    amplitude: float = Field(ge=0)
    min_nm: float = Field(gt=0)
    max_nm: float = Field(gt=0)
    center_nm: float = Field(gt=0)
    width_nm: float = Field(gt=0)
    flat_width_nm: float = Field(ge=0)
    edge_width_nm: float = Field(ge=0)

    @model_validator(mode="after")
    def valid(self):
        if self.max_nm <= self.min_nm:
            raise ValueError("Basic spectrum max_nm must exceed min_nm")
        if self.shape == "cosine_flat" and self.flat_width_nm+2*self.edge_width_nm <= 0:
            raise ValueError("Cosine flat-top requires positive total width")
        return self


class CurveSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mode: Literal["basic","csv","manual","standard"]
    basic: BasicCurve
    interpolation: Literal["pchip","linear"]
    csv_points: list[Point]
    manual_points: list[Point]
    csv_name: str

    @model_validator(mode="after")
    def valid(self):
        for key in ("csv_points","manual_points"):
            points=getattr(self,key)
            if points and (len(points)<2 or any(b.wavelength_nm<=a.wavelength_nm for a,b in zip(points,points[1:]))):
                raise ValueError(f"{key} needs at least two strictly increasing wavelengths")
        if self.mode in ("csv","manual") and not getattr(self,self.mode+"_points"):
            raise ValueError(f"{self.mode} mode has no applied points")
        return self


class SpectralInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filter: CurveSpec
    other: CurveSpec
    pde: CurveSpec
    solar: CurveSpec

    @model_validator(mode="after")
    def valid(self):
        for name in ("filter","other","pde"):
            curve=getattr(self,name)
            if curve.mode=="standard":
                raise ValueError("Standard spectrum mode is only available for solar")
        for name in ("filter","pde"):
            curve=getattr(self,name)
            if curve.basic.amplitude>1 or any(p.value>1 for p in curve.csv_points+curve.manual_points):
                raise ValueError(f"{name} probability/transmission must be within 0..1")
        return self


def merge_config(base, overrides):
    result=deepcopy(base)
    for key,value in overrides.items():
        result[key]=merge_config(result[key],value) if isinstance(value,dict) and isinstance(result.get(key),dict) else deepcopy(value)
    return result


class Curve:
    def __init__(self,spec):
        self.spec=spec
        self.has_samples=spec.mode in ("csv","manual")
        self.polynomial=None
        if self.has_samples:
            points=getattr(spec,spec.mode+"_points")
            self.x=np.array([p.wavelength_nm for p in points])
            self.y=np.array([p.value for p in points])
            self.method=spec.interpolation
            if self.method=="pchip":
                self.polynomial=PchipInterpolator(self.x,self.y,extrapolate=False)
        elif spec.mode=="basic":
            self.x=np.array([spec.basic.min_nm,spec.basic.max_nm])
            self.y=np.array([])
            self.method=spec.basic.shape
        else:
            raise ValueError("Standard solar spectrum is evaluated by the reference-data module")
        self.wavelength=self.x
        self.transmission=self.y

    def evaluate(self,wavelength_nm):
        x=np.asarray(wavelength_nm,dtype=float)
        if self.has_samples:
            y=self.polynomial(x) if self.polynomial is not None else np.interp(x,self.x,self.y)
        else:
            b=self.spec.basic
            distance=np.abs(x-b.center_nm)
            if b.shape=="constant": y=np.ones_like(x)
            elif b.shape=="rectangle": y=(distance<=b.width_nm/2).astype(float)
            elif b.shape=="gaussian": y=np.exp(-4*np.log(2)*((x-b.center_nm)/b.width_nm)**2)
            elif b.edge_width_nm==0: y=(distance<=b.flat_width_nm/2).astype(float)
            else:
                u=np.clip((distance-b.flat_width_nm/2)/b.edge_width_nm,0,1)
                y=(1+np.cos(np.pi*u))/2
            y=y*b.amplitude
        result=np.where((x>=self.x[0])&(x<=self.x[-1]),y,0)
        return float(result) if result.ndim==0 else result

    __call__=evaluate

    def knots(self,algorithms=None):
        if self.has_samples: return self.x
        a=algorithms or Algorithms.load()
        b=self.spec.basic
        parts=[*self.x,b.center_nm]
        if b.shape=="rectangle":
            parts.extend([b.center_nm-b.width_nm/2,b.center_nm+b.width_nm/2])
        elif b.shape=="gaussian":
            parts.extend(b.center_nm+b.width_nm*np.linspace(-a.basic_gaussian_extent_fwhm,a.basic_gaussian_extent_fwhm,a.basic_quadrature_segments+1))
        elif b.shape=="cosine_flat":
            ramp=b.flat_width_nm/2+np.linspace(0,b.edge_width_nm,a.basic_quadrature_segments+1)
            parts.extend(b.center_nm+ramp);parts.extend(b.center_nm-ramp)
        values=np.unique(parts)
        return values[(values>=self.x[0])&(values<=self.x[-1])]

    def integral_nm(self):
        if self.polynomial is not None:
            return float(self.polynomial.integrate(*self.x[[0,-1]]))
        if self.has_samples:
            return float(np.trapezoid(self.y,self.x))
        b=self.spec.basic
        lo,hi=self.x
        if b.shape=="constant": return b.amplitude*(hi-lo)
        if b.shape=="rectangle" or b.shape=="cosine_flat" and b.edge_width_nm==0:
            width=b.width_nm if b.shape=="rectangle" else b.flat_width_nm
            return b.amplitude*max(0,min(hi,b.center_nm+width/2)-max(lo,b.center_nm-width/2))
        if b.shape=="gaussian":
            k=2*np.sqrt(np.log(2))/b.width_nm
            return float(b.amplitude*np.sqrt(np.pi)/(2*k)*(erf(k*(hi-b.center_nm))-erf(k*(lo-b.center_nm))))
        def primitive(t):
            z=abs(t);flat=b.flat_width_nm/2
            u=min(max(z-flat,0),b.edge_width_nm)
            integral=min(z,flat)+(u+b.edge_width_nm/np.pi*np.sin(np.pi*u/b.edge_width_nm))/2
            return np.sign(t)*integral
        return float(b.amplitude*(primitive(hi-b.center_nm)-primitive(lo-b.center_nm)))

    def plot_knots(self,algorithms=None):
        # Include both sides of ideal discontinuities so the rendered edge is vertical.
        knots=self.knots(algorithms)
        if not self.has_samples and self.method in ("constant","rectangle","cosine_flat"):
            eps=np.r_[np.nextafter(knots,-np.inf),np.nextafter(knots,np.inf)]
            knots=np.unique(np.r_[knots,eps])
        return knots
