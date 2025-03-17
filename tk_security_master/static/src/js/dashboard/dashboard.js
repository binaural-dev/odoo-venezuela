/** @odoo-module **/
import {registry} from "@web/core/registry";
import {Layout} from "@web/search/layout";
import {getDefaultConfig} from "@web/views/view";
import {useService} from "@web/core/utils/hooks";
import {Domain} from "@web/core/domain";
import {sprintf} from "@web/core/utils/strings";

const {Component, useSubEnv, useState, onMounted, onWillStart, useRef} = owl;
import {loadJS, loadCSS} from "@web/core/assets"

class TKSecurityMasterDashboard extends Component {
    setup() {
        this.state = useState({
            sessionCounts: {
                'chrome': 0,
                'safari': 0,
                'edge': 0,
                'opera': 0,
                'firefox': 0,
                'other': 0,
                'all': 0,
                'active': 0,
                'terminate': 0
            },
            osCounts: {'windows': 0, 'mac': 0, 'linux': 0, 'android': 0, 'ios': 0, 'other_os': 0}
        });

        useSubEnv({
            config: {
                ...getDefaultConfig(),
                ...this.env.config,
            },
        });
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.orm = useService("orm");
        this.worldMap = useRef('worldMap');
        this.sessionOS = useRef('sessionOS');

        onWillStart(async () => {
            await loadJS('tk_security_master/static/src/lib/index.js');
            await loadJS('tk_security_master/static/src/lib/map.js');
            await loadJS('tk_security_master/static/src/lib/xy.js');
            await loadJS('tk_security_master/static/src/lib/worldLow.js');
            await loadJS('tk_security_master/static/src/lib/Animated.js');

            const sessionsData = await this.orm.call('user.sign.in.details', 'get_browser_wise_session_stats', []);
            if (sessionsData) {
                this.state.sessionCounts = sessionsData;
                this.state.osCounts = sessionsData['os'];
            }
        });

        onMounted(async () => {
            let userSessionStats = await this.orm.call('user.sign.in.details', 'get_users_sessions_stats', []);
            this.renderMapWiseSessionChart(this.worldMap.el, userSessionStats);
            this.renderSessionOSChart(this.sessionOS.el, this.state.osCounts);
        })
    }

    viewSessions(type) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: "Sessions",
            res_model: 'user.sign.in.details',
            view_mode: 'list',
            views: [[false, 'list'], [false, 'form']],
            target: 'current',
            context: {},
            domain: [['browser', '=', type]],
        });
    }

    viewSessionsData(type) {
        let domain = false
        if (type === 'all') {
            domain = [['active', 'in', [true, false]]]
        } else if (type === 'active') {
            domain = [['active', '=', true]]
        } else {
            domain = [['active', '=', false]]
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: "Sessions",
            res_model: 'user.sign.in.details',
            view_mode: 'list',
            views: [[false, 'list'], [false, 'form']],
            target: 'current',
            context: {},
            domain: domain,
        });
    }

    renderMapWiseSessionChart(div, sessionData) {
        const root = am5.Root.new(div);
        root.setThemes([am5themes_Animated.new(root)]);
        const chart = root.container.children.push(
            am5map.MapChart.new(root, {
                panX: "rotateX",
                panY: "translateY",
                projection: am5map.geoMercator(),
            })
        );
        chart.set("zoomControl", am5map.ZoomControl.new(root, {}));
        const polygonSeries = chart.series.push(
            am5map.MapPolygonSeries.new(root, {
                geoJSON: am5geodata_worldLow,
                exclude: ["AQ"]
            })
        );
        polygonSeries.mapPolygons.template.setAll({
            fill: am5.color(0xdadada)
        });
        const pointSeries = chart.series.push(am5map.ClusteredPointSeries.new(root, {}));

        pointSeries.set("clusteredBullet", function (root) {
            const container = am5.Container.new(root, {
                cursorOverStyle: "pointer"
            });
            const circle1 = container.children.push(am5.Circle.new(root, {
                radius: 8,
                tooltipY: 0,
                fill: am5.color(0xff8c00)
            }));
            const circle2 = container.children.push(am5.Circle.new(root, {
                radius: 12,
                fillOpacity: 0.3,
                tooltipY: 0,
                fill: am5.color(0xff8c00)
            }));
            const circle3 = container.children.push(am5.Circle.new(root, {
                radius: 16,
                fillOpacity: 0.3,
                tooltipY: 0,
                fill: am5.color(0xff8c00)
            }));
            const label = container.children.push(am5.Label.new(root, {
                centerX: am5.p50,
                centerY: am5.p50,
                fill: am5.color(0xffffff),
                populateText: true,
                fontSize: "8",
                text: "{value}"
            }));
            container.events.on("click", function (e) {
                pointSeries.zoomToCluster(e.target.dataItem);
            });
            return am5.Bullet.new(root, {
                sprite: container
            });
        });
        pointSeries.bullets.push(function () {
            const circle = am5.Circle.new(root, {
                radius: 6,
                tooltipY: 0,
                fill: am5.color(0xff8c00),
                tooltipText: "{title}"
            });
            return am5.Bullet.new(root, {
                sprite: circle
            });
        });
        const cities = [
            {title: "Vienna \nMac OS \nIP: 192.168.1.1", latitude: 48.2092, longitude: 16.3728},
            {title: "Minsk", latitude: 53.9678, longitude: 27.5766},
            {title: "Brussels", latitude: 50.8371, longitude: 4.3676},
            {title: "Sarajevo", latitude: 43.8608, longitude: 18.4214},
            {title: "Sofia", latitude: 42.7105, longitude: 23.3238},
        ];
        for (let i = 0; i < sessionData.length; i++) {
            const city = sessionData[i];
            addCity(city.longitude, city.latitude, city.title);
        }

        function addCity(longitude, latitude, title) {
            pointSeries.data.push({
                geometry: {type: "Point", coordinates: [longitude, latitude]},
                title: title
            });
        }
        chart.appear(1000, 100);
    }

    renderSessionOSChart(div, sessionData) {
        const root = am5.Root.new(div);
        root.setThemes([
            am5themes_Animated.new(root)
        ]);

        const data = [{
            name: "Mac OS",
            steps: sessionData['mac'],
            pictureSettings: {
                src: "tk_security_master/static/src/img/mac.svg"
            }
        }, {
            name: "Windows",
            steps: sessionData['windows'],
            pictureSettings: {
                src: "tk_security_master/static/src/img/windowsOS.svg"
            }
        }, {
            name: "iOS",
            steps: sessionData['ios'],
            pictureSettings: {
                src: "tk_security_master/static/src/img/ios.svg"
            }
        }, {
            name: "Android",
            steps: sessionData['android'],
            pictureSettings: {
                src: "tk_security_master/static/src/img/androidOS.svg"
            }
        }, {
            name: "Linux",
            steps: sessionData['linux'],
            pictureSettings: {
                src: "tk_security_master/static/src/img/linux.svg"
            }
        }, {
            name: "Other",
            steps: sessionData['other_os'],
            pictureSettings: {
                src: "tk_security_master/static/src/img/os.svg"
            }
        }];
        const chart = root.container.children.push(
            am5xy.XYChart.new(root, {
                panX: false,
                panY: false,
                wheelX: "none",
                wheelY: "none",
                paddingBottom: 50,
                paddingTop: 40,
                paddingLeft: 0,
                paddingRight: 0
            })
        );
        const xRenderer = am5xy.AxisRendererX.new(root, {
            minorGridEnabled: true,
            minGridDistance: 60
        });
        xRenderer.grid.template.set("visible", false);
        const xAxis = chart.xAxes.push(
            am5xy.CategoryAxis.new(root, {
                paddingTop: 40,
                categoryField: "name",
                renderer: xRenderer
            })
        );


        const yRenderer = am5xy.AxisRendererY.new(root, {});
        yRenderer.grid.template.set("strokeDasharray", [3]);
        const yAxis = chart.yAxes.push(
            am5xy.ValueAxis.new(root, {
                min: 0,
                renderer: yRenderer
            })
        );
        const series = chart.series.push(
            am5xy.ColumnSeries.new(root, {
                name: "Income",
                xAxis: xAxis,
                yAxis: yAxis,
                valueYField: "steps",
                categoryXField: "name",
                sequencedInterpolation: true,
                calculateAggregates: true,
                maskBullets: false,
                tooltip: am5.Tooltip.new(root, {
                    dy: -30,
                    pointerOrientation: "vertical",
                    labelText: "{valueY}"
                })
            })
        );
        series.columns.template.setAll({
            strokeOpacity: 0,
            cornerRadiusBR: 10,
            cornerRadiusTR: 10,
            cornerRadiusBL: 10,
            cornerRadiusTL: 10,
            maxWidth: 50,
            fillOpacity: 0.8
        });

        let currentlyHovered;
        series.columns.template.events.on("pointerover", function (e) {
            handleHover(e.target.dataItem);
        });
        series.columns.template.events.on("pointerout", function (e) {
            handleOut();
        });

        function handleHover(dataItem) {
            if (dataItem && currentlyHovered !== dataItem) {
                handleOut();
                currentlyHovered = dataItem;
                const bullet = dataItem.bullets[0];
                bullet.animate({
                    key: "locationY",
                    to: 1,
                    duration: 600,
                    easing: am5.ease.out(am5.ease.cubic)
                });
            }
        }

        function handleOut() {
            if (currentlyHovered) {
                const bullet = currentlyHovered.bullets[0];
                bullet.animate({
                    key: "locationY",
                    to: 0,
                    duration: 600,
                    easing: am5.ease.out(am5.ease.cubic)
                });
            }
        }
        const circleTemplate = am5.Template.new({});

        series.bullets.push(function (root, series, dataItem) {
            const bulletContainer = am5.Container.new(root, {});
            const circle = bulletContainer.children.push(
                am5.Circle.new(
                    root,
                    {
                        radius: 34
                    },
                    circleTemplate
                )
            );
            const maskCircle = bulletContainer.children.push(
                am5.Circle.new(root, {radius: 27})
            );
            const imageContainer = bulletContainer.children.push(
                am5.Container.new(root, {
                    mask: maskCircle
                })
            );
            const image = imageContainer.children.push(
                am5.Picture.new(root, {
                    templateField: "pictureSettings",
                    centerX: am5.p50,
                    centerY: am5.p50,
                    width: 60,
                    height: 60
                })
            );
            return am5.Bullet.new(root, {
                locationY: 0,
                sprite: bulletContainer
            });
        });
        series.set("heatRules", [
            {
                dataField: "valueY",
                min: am5.color(0xe5dc36),
                max: am5.color(0x5faa46),
                target: series.columns.template,
                key: "fill"
            },
            {
                dataField: "valueY",
                min: am5.color(0xe5dc36),
                max: am5.color(0x5faa46),
                target: circleTemplate,
                key: "fill"
            }
        ]);

        series.data.setAll(data);
        xAxis.data.setAll(data);
        const cursor = chart.set("cursor", am5xy.XYCursor.new(root, {}));
        cursor.lineX.set("visible", false);
        cursor.lineY.set("visible", false);
        cursor.events.on("cursormoved", function () {
            const dataItem = series.get("tooltip").dataItem;
            if (dataItem) {
                handleHover(dataItem);
            } else {
                handleOut();
            }
        });
        series.appear();
        chart.appear(1000, 100);

    }

}

TKSecurityMasterDashboard.template = "tk_security_master.master_dashboard";
registry.category("actions").add("tk_security_master_dashboard", TKSecurityMasterDashboard);
