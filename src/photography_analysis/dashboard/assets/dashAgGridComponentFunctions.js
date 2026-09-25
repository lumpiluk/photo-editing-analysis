const dagcomponentfuncs = window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

dagcomponentfuncs.PersonLinksRenderer = function (props) {
    const uid = props.data.id;
    const immichHost = props.context.immichHost;

    return React.createElement(
        "div",
        { style: { display: "flex", gap: ".5em" } },
        React.createElement(
            "a",
            { href: `/people-detail?ids=${uid}`, title: "View details" },
            "🔍"  // swap for your custom icon
        ),
        React.createElement(
            "a",
            {
                href: Object.hasOwn(props.data, 'ids') ?
                    `${immichHost}/search?query={"personIds"%3A[${props.data.ids.map((it) => `"${it}"`).join("%2C")}]}`
                    : `${immichHost}/people/${uid}`,
                target: "_blank",
                title: "Open in Immich"
            },
            "🖼️"  // stand-in for the Immich icon
        )
    );
};
