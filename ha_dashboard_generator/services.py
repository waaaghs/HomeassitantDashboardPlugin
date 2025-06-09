"""Services for Chart Generator integration."""
import logging
import os
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List

import voluptuous as vol
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
from homeassistant.components.recorder import get_instance, history

from .const import (
    DOMAIN,
    SERVICE_GENERATE_CHART,
    DEFAULT_CHART_WIDTH,
    DEFAULT_CHART_HEIGHT,
    DEFAULT_CHART_DPI,
    CHART_TYPES
)

_LOGGER = logging.getLogger(__name__)

GENERATE_CHART_SCHEMA = vol.Schema({
    vol.Required("entities"): cv.ensure_list,
    vol.Optional("chart_type", default="line"): vol.In(CHART_TYPES),
    vol.Optional("filename"): cv.string,
    vol.Optional("title"): cv.string,
    vol.Optional("hours_to_show", default=24): cv.positive_int,
    vol.Optional("width", default=DEFAULT_CHART_WIDTH): cv.positive_int,
    vol.Optional("height", default=DEFAULT_CHART_HEIGHT): cv.positive_int,
    vol.Optional("dpi", default=DEFAULT_CHART_DPI): cv.positive_int,
    vol.Optional("y_label"): cv.string,
    vol.Optional("show_legend", default=True): cv.boolean,
})

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Chart Generator."""
    
    async def generate_chart_service(call: ServiceCall) -> None:
        """Generate a chart from entity data."""
        entities = call.data["entities"]
        chart_type = call.data["chart_type"]
        filename = call.data.get("filename", f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        title = call.data.get("title", "Home Assistant Chart")
        hours_to_show = call.data["hours_to_show"]
        width = call.data["width"]
        height = call.data["height"]
        dpi = call.data["dpi"]
        y_label = call.data.get("y_label", "Value")
        show_legend = call.data["show_legend"]
        
        try:
            # Get historical data
            end_time = dt_util.utcnow()
            start_time = end_time - timedelta(hours=hours_to_show)
            
            # Run in executor to avoid blocking the event loop
            chart_data = await hass.async_add_executor_job(
                _get_entity_history, hass, entities, start_time, end_time
            )
            
            if not chart_data:
                _LOGGER.error("No data found for entities: %s", entities)
                return
            
            # Generate chart in executor
            await hass.async_add_executor_job(
                _create_chart, 
                chart_data, 
                chart_type, 
                filename, 
                title, 
                width, 
                height, 
                dpi, 
                y_label, 
                show_legend,
                hass
            )
            
            _LOGGER.info("Chart generated successfully: %s", filename)
            
        except Exception as e:
            _LOGGER.error("Error generating chart: %s", e)
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_CHART,
        generate_chart_service,
        schema=GENERATE_CHART_SCHEMA,
    )

def _get_entity_history(hass: HomeAssistant, entities: List[str], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """Get historical data for entities."""
    try:
        recorder_instance = get_instance(hass)
        
        # Get history data
        history_data = history.state_changes_during_period(
            hass, start_time, end_time, str_entity_ids=entities
        )
        
        chart_data = {}
        
        for entity_id in entities:
            if entity_id not in history_data:
                continue
                
            states = history_data[entity_id]
            
            times = []
            values = []
            
            for state in states:
                try:
                    # Try to convert state to float
                    value = float(state.state)
                    times.append(state.last_changed)
                    values.append(value)
                except (ValueError, TypeError):
                    # Skip non-numeric states
                    continue
            
            if times and values:
                chart_data[entity_id] = {
                    'times': times,
                    'values': values,
                    'friendly_name': hass.states.get(entity_id).attributes.get('friendly_name', entity_id)
                }
        
        return chart_data
        
    except Exception as e:
        _LOGGER.error("Error getting entity history: %s", e)
        return {}

def _create_chart(chart_data: Dict[str, Any], chart_type: str, filename: str, 
                 title: str, width: int, height: int, dpi: int, 
                 y_label: str, show_legend: bool, hass: HomeAssistant) -> None:
    """Create and save the chart."""
    
    # Set up the plot
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(chart_data)))
    
    if chart_type == "line":
        for i, (entity_id, data) in enumerate(chart_data.items()):
            ax.plot(data['times'], data['values'], 
                   label=data['friendly_name'], 
                   color=colors[i], 
                   linewidth=2)
        
        # Format x-axis for time
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        plt.xticks(rotation=45)
        
    elif chart_type == "bar":
        # For bar charts, use the latest values
        entities = list(chart_data.keys())
        latest_values = [chart_data[entity]['values'][-1] if chart_data[entity]['values'] else 0 
                        for entity in entities]
        friendly_names = [chart_data[entity]['friendly_name'] for entity in entities]
        
        bars = ax.bar(friendly_names, latest_values, color=colors[:len(entities)])
        plt.xticks(rotation=45, ha='right')
        
    elif chart_type == "scatter":
        for i, (entity_id, data) in enumerate(chart_data.items()):
            ax.scatter(data['times'], data['values'], 
                      label=data['friendly_name'], 
                      color=colors[i], 
                      alpha=0.7)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        plt.xticks(rotation=45)
        
    elif chart_type == "histogram":
        all_values = []
        for data in chart_data.values():
            all_values.extend(data['values'])
        
        ax.hist(all_values, bins=20, alpha=0.7, color=colors[0])
        ax.set_xlabel(y_label)
        ax.set_ylabel('Frequency')
        
    elif chart_type == "pie":
        # Use latest values for pie chart
        entities = list(chart_data.keys())
        latest_values = [chart_data[entity]['values'][-1] if chart_data[entity]['values'] else 0 
                        for entity in entities]
        friendly_names = [chart_data[entity]['friendly_name'] for entity in entities]
        
        # Filter out zero values
        non_zero_data = [(name, value) for name, value in zip(friendly_names, latest_values) if value > 0]
        if non_zero_data:
            names, values = zip(*non_zero_data)
            ax.pie(values, labels=names, autopct='%1.1f%%', colors=colors[:len(values)])
        
    # Set labels and title
    ax.set_title(title, fontsize=16, fontweight='bold')
    
    if chart_type not in ["pie", "histogram"]:
        ax.set_ylabel(y_label)
    
    if chart_type in ["line", "scatter"] and show_legend:
        ax.legend()
    
    # Improve layout
    plt.tight_layout()
    
    # Save to share folder
    share_path = "/share"
    if not os.path.exists(share_path):
        share_path = "/config/www"  # Fallback to www folder
        
    file_path = os.path.join(share_path, filename)
    
    try:
        plt.savefig(file_path, dpi=dpi, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        _LOGGER.info("Chart saved to: %s", file_path)
    except Exception as e:
        _LOGGER.error("Error saving chart to %s: %s", file_path, e)
        plt.close()