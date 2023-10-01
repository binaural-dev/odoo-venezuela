{
    "name": "Zmart Reporte RMA",
    "summary": "Modulo para imprimir el reporte rma",
    "version": "16.0.0.2",
    "category": "RMA",
    "author": "BinauraDev",
    "license": "AGPL-3",
    "depends": ["rma","stock","sale_zmart"],
    "data": [
        "data/paperformat.xml",
        "views/rma_views.xml",
        "views/stock_picking.xml",
        "report/note_rma.xml",
        "report/picking_rma_report.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}